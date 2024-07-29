# Emma

Emma is an agent designed to help you interact with Infrahub.

Currently, Emma can help you to:

- Import CSV Data into Infrahub
- Export Data from Infrahub in CSV format
- Build, Load, and Visualize Infrahub schema

![Home page](static/home_page.png)

## Quick Start

### Running Locally with Poetry

To run Emma locally using Poetry, follow these steps:

1. **Install Dependencies:**

 ```console
 poetry install
 ```

1. **Run the Application:**

 ```console
 poetry shell
 streamlit run main.py
 ```

1. **Set Environment Variables:**

 Emma uses Infrahub standard environment variables to connect to Infrahub:

 ```console
 export INFRAHUB_ADDRESS="http://localhost:8000"
 export INFRAHUB_API_TOKEN="06438eb2-8019-4776-878c-0941b1f1d1ec"
 ```

### Running with Docker Compose

To run Emma using Docker Compose, follow these steps:

1. **Build and Run the Application:**

 ```console
 docker-compose up --build
 ```

### Connecting to Infrahub Network

If you run Infrahub as another container in the local network, you need to connect Emma to it. After starting both containers, run the following command:

```console
docker network connect <infrahub-network> emma-emma-1
```

## Screenshots

![Schema builder](static/schema_builder.png)
![Schema visualizer](static/schema_visualizer.png)
![Data exporter](static/data_exporter.png)
![Schema loader](static/schema_loader.png)
