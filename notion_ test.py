from notion_client import Client

notion = Client(auth="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")

db_id = "1cb383340afe8014b1a5d6aed5192836"
res = notion.databases.retrieve(db_id)
print(res)
