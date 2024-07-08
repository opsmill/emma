# Emma

Emma is an agent designed to help you interact with Infrahub.

Currently Emma can help you to :
- Import CSV Data into Infrahub
- Export Data from Infrahub in CSV format

## Install

```
poetry install
```

## Launch

Emma is using Infrahub standard environment variables to connect to Infrahub `INFRAHUB_ADDRESS` & `INFRAHUB_API_TOKEN`

```
poetry shell
streamlit run main.py
```

