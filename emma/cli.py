from asyncio import run as aiorun
import nltk 
import typer
from pathlib import Path
from thefuzz import fuzz
from thefuzz import process
from rich import print as rprint
from rich import inspect as rinspect
from pydantic import BaseModel
from collections import defaultdict
app = typer.Typer(name="Emma", pretty_exceptions_enable=False)


# class GlobalRatios(BaseModel):


# class BlockRatio(BaseModel):
#     block_id: int
#     ratios: dict[str, dict[int, int]] = defaultdict(lambda: dict())

# class FileRatio:
#     name: str
#     blocks: list[BlockRatio]

class TextBlock(BaseModel):
    block_id: int
    content: str
    start_line: int
    end_line: int
    block_ratios: dict[int, int] = {}
    global_ratios: dict[str, dict[int, int]] = defaultdict(lambda: dict())
    clusters: set[int] = set()

    def local_matching_blocks(self, threshold: int = 75) -> set[int]:
        matches: set[int] = set()

        for block_id, ratio in self.block_ratios.items():
            if ratio > threshold:
                matches.add(block_id)

        return matches

    def global_matching_blocks(self, threshold: int = 75) -> set[tuple[str, int]]:

        matches: set[tuple[str, int]] = set()

        for file_name, blocks in self.global_ratios.items():
            for block_id, ratio in blocks.items():
                if ratio > threshold:
                 matches.add((file_name, block_id))

        return matches

class ClusterBlock(BaseModel):
    block_ids: list[int]
    cluster_id: int

class GlobalCluster(BaseModel):
    block_ids: list[tuple[str, int]]
    cluster_id: int



class TextFile(BaseModel):
    file: Path
    content: str
    blocks: list[TextBlock] = []
    clusters: list[ClusterBlock] = []

    @property
    def nbr_lines(self):
        return len(self.content.splitlines())

    @classmethod
    def create(cls, file: Path):

        obj = cls(file=file, content=file.read_text())
        tokens: list[str] = nltk.blankline_tokenize(obj.content)

        line_nbr = 0
        for idx, token in enumerate(tokens):
            nbr_lines = len(token.splitlines())
            obj.blocks.append(
                TextBlock(block_id=idx, content=token, start_line=line_nbr, end_line=line_nbr+nbr_lines-1)
            )
            line_nbr += nbr_lines + 1

        obj._calculate_block_ratios()

        obj._calculate_clusters()

        return obj

    def print_blocks(self):
        for block in self.blocks:
            print(f"---- {block.block_id} {block.start_line} {block.end_line}  ----")
            print(block.content)
            print("--------")

    def print(self):
        for idx, line in enumerate(self.content.splitlines()):
            print(f"{idx} | {line}")

    def _calculate_block_ratios(self):
        for block_a in self.blocks:
            for block_b in self.blocks:
                if block_a.block_id == block_b.block_id:
                    continue
                if block_a.block_id in block_b.block_ratios.keys() or  block_b.block_id in block_a.block_ratios.keys():
                    continue

                ratio = fuzz.ratio(block_a.content, block_b.content)
                block_a.block_ratios[block_b.block_id] = ratio
                block_b.block_ratios[block_a.block_id] = ratio

    def _calculate_clusters(self):

        for block in self.blocks:
            intersec = block.local_matching_blocks()

            if not intersec:
                continue

            intersec.add(block.block_id)
            matching_ids: dict[int, set[int]] = {}
            for matching_block_id in block.local_matching_blocks():
                matching_ids[matching_block_id] = self.blocks[matching_block_id].local_matching_blocks()
                matching_ids[matching_block_id].add(matching_block_id)

            for _, matching_block in matching_ids.items():
                intersec = intersec & matching_block

            # If we still have some values at the end, all blocks are part of a cluster
            if len(intersec) > 1:
                similar_cluster_already_exist = False
                for cluster in self.clusters:
                    if set(cluster.block_ids) == intersec:
                        similar_cluster_already_exist = True
                        break

                if similar_cluster_already_exist:
                    continue

                cluster_id = len(self.clusters)
                cluster = ClusterBlock(cluster_id=cluster_id, block_ids=list(intersec))
                self.clusters.append(cluster)

                for block_id in intersec:
                    self.blocks[block_id].clusters.add(cluster_id)


class FilesAnalyzer(BaseModel):
    files: dict[str, TextFile] = {}
    clusters: list[GlobalCluster] = []

    def print_cluster(self, id: int):

        cluster = self.clusters[id]

        for file_name, block_id in cluster.block_ids:
            print(f" --- {file_name} - {block_id} --- ")
            print(self.files[file_name].blocks[block_id].content)


    def analyze(self):

        # Calculate Ratios
        for file1 in self.files.values():
            for file2 in self.files.values():
                if file1.file.name == file2.file.name:
                    continue
                self.calculate_global_ratios(file1=file1, file2=file2)

        # Identify Clusters
        self.calculate_global_cluster()

    @staticmethod
    def calculate_global_ratios(file1: TextFile, file2: TextFile):

        for block_1 in file1.blocks:
            for block_2 in file2.blocks:

                if block_1.block_id in block_2.global_ratios[file1.file.name].keys() or block_2.block_id in block_1.global_ratios[file2.file.name].keys():
                    continue

                ratio = fuzz.ratio(block_1.content, block_2.content)
                block_1.global_ratios[file2.file.name][block_2.block_id] = ratio
                block_2.global_ratios[file1.file.name][block_1.block_id] = ratio


    def calculate_global_cluster(self):

        for file in self.files.values():
            for block in file.blocks:
                intersec = block.global_matching_blocks()

                if not intersec:
                    continue

                intersec.add((file.file.name, block.block_id))

                matching_ids: dict[int, set[int]] = {}
                for file_name, block_id in block.global_matching_blocks():
                    matching_ids[(file_name, block_id)] = self.files[file_name].blocks[block_id].global_matching_blocks()
                    matching_ids[(file_name, block_id)].add((file_name, block_id))

                for _, matching_block in matching_ids.items():
                    intersec = intersec & matching_block

                # If we still have some values at the end, all blocks are part of a cluster
                if len(intersec) > 1:
                    similar_cluster_already_exist = False
                    for cluster in self.clusters:
                        if set(cluster.block_ids) == intersec:
                            similar_cluster_already_exist = True
                            break

                    if similar_cluster_already_exist:
                        continue

                    cluster_id = len(self.clusters)
                    cluster = GlobalCluster(cluster_id=cluster_id, block_ids=list(intersec))
                    self.clusters.append(cluster)

                    # for block_id in intersec:
                    #     self.blocks[block_id].clusters.add(cluster_id)


@app.command()
def ping(directory: Path = typer.Argument(...)) -> None:
    print("echo")

@app.command()
def analyze_files(directory: Path = typer.Argument(None), nbr_files: int = 3) -> None:
    directory_path = Path('/Users/damien/projects/pulse-ai/configs/company1')
    text_files = [ item for item in directory_path.glob('leaf*.conf')]

    fa = FilesAnalyzer()
    for text_file in text_files[:nbr_files]:
        fa.files[text_file.name] = TextFile.create(file=text_file)

    print(f"Loaded {len(fa.files)} files")

    text_file = fa.files[text_files[0].name]

    fa.analyze()

        # go over the block that are not part of a cluster and see if there is a match


    # def calculate_global_cluster(files: dict[str, TextFile]):

    #     for file in files.values():
    #         for block in file.blocks:
    #             intersec = block.global_matching_blocks()

    #             if not intersec:
    #                 continue

    #             intersec.add((file.file.name, block.block_id))

    #             matching_ids: dict[int, set[int]] = {}
    #             for file_name, block_id in block.global_matching_blocks():
    #                 matching_ids[(file_name, block_id)] = files[file_name].blocks[block_id].global_matching_blocks()
    #                 matching_ids[(file_name, block_id)].add((file_name, block_id))

    #             for _, matching_block in matching_ids.items():
    #                 intersec = intersec & matching_block

    #             # If we still have some values at the end, all blocks are part of a cluster
    #             if len(intersec) > 1:
    #                 similar_cluster_already_exist = False
    #                 for cluster in clusters:
    #                     if set(cluster.block_ids) == intersec:
    #                         similar_cluster_already_exist = True
    #                         break

    #                 if similar_cluster_already_exist:
    #                     continue

    #                 cluster_id = len(clusters)
    #                 cluster = GlobalCluster(cluster_id=cluster_id, block_ids=list(intersec))
    #                 clusters.append(cluster)

    #                 # for block_id in intersec:
    #                 #     self.blocks[block_id].clusters.add(cluster_id)

    # calculate_global_cluster(files=file_contents)

    breakpoint()
