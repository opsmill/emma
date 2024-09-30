from infrahub_sdk import InfrahubClientSync
import os
from tqdm import tqdm

client = InfrahubClientSync()

site = client.create(kind="LocationSite", name="test")
site.save(allow_upsert=True)

# Walk through the directory and grab the files
for dirpath, _, filenames in tqdm(os.walk("test_data")):
    for filename in filenames:
        if filename.endswith(".conf"):
            print(filename)
            device_name = filename.replace(".conf", "").replace(".", "-")
            full_path = os.path.join(dirpath, filename)

            with open(full_path, "r") as f:
                config = f.read()

            config_object = client.object_store.upload(content=config)

            # Use full_path if needed or just filename/device_name for the client.create call
            device = client.create(
                kind="InfraDevice",
                name=device_name,
                hostname=device_name,
                branch="main",
                location=site,
                site="test",
                type="cisco",
                config_object_store_id=config_object["identifier"],
                object_store_id=config_object["identifier"]
            )
            device.save(allow_upsert=True)
