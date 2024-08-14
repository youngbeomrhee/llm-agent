import json


def print_json_error(json_string):
    try:
        json.loads(json_string)
    except json.JSONDecodeError as e:
        print(f"エラー: {e}")
        print(f"エラー位置: {e.pos}")
        print(f"エラー行: {e.lineno}")
        print(f"エラー列: {e.colno}")
        print("エラー周辺の文字列:")
        start = max(0, e.pos - 20)
        end = min(len(json_string), e.pos + 20)
        print(json_string[start:end])


with open("chapter09/tmp/checkpoint.json", "r", encoding="utf-8") as file:
    json_string = file.read()

print_json_error(json_string)
