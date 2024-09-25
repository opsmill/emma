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
            # Use full_path if needed or just filename/device_name for the client.create call
            device = client.create(kind="InfraDevice", name=device_name, hostname=device_name, branch="main", location=site, site="test", type="cisco")
            device.save()
