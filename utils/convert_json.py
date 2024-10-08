import json


def convert_format_glm3(json_path, output_path):
    """
    转换为chatglm3官方展示的多轮对话训练格式，详情见：https://github.com/THUDM/ChatGLM3/blob/main/finetune_demo/README.md
    :param output_path: 输出json文件位置
    :param json_path: 原始json文件位置
    """

    def transform_conversations_2(conversations):
        transformed_conversations = []
        for conv in conversations:
            transformed_conversations.append({"role": conv["role"], "content": conv["content"]})
        return transformed_conversations

    # 读取输入JSON文件
    with open(json_path, 'r', encoding='utf-8') as input_file:
        input_json = json.load(input_file)

    # 转换数据
    output_data = []
    for item in input_json:
        transformed_item = {"conversations": transform_conversations_2(item["conversations"])}
        output_data.append(transformed_item)

    # 写入输出JSON文件
    with open(output_path, 'w', encoding='utf-8') as output_file:
        for entry in output_data:
            json_line = json.dumps(entry, ensure_ascii=False)
            output_file.write(json_line + '\n')

    print(f"转换完成，结果已写入 {output_path}")


def convert_format_swift(input_file_path, output_file_path):
    """
    swift微调数据格式的json文件转换
    :param input_file_path:原始json文件位置
    :param output_file_path:输出json文件位置
    """
    # 定义转换函数
    def transform_conversations(conversations):
        transformed_conversations = []
        for conv in conversations:
            transformed_conversations.append({"from": conv["role"], "value": conv["content"]})
        return transformed_conversations

    # 读取输入JSON文件
    with open(input_file_path, 'r', encoding='utf-8') as input_file:
        input_json = json.load(input_file)

    # 转换数据
    output_data = []
    for item in input_json:
        transformed_item = {"conversations": transform_conversations(item["conversations"])}
        output_data.append(transformed_item)

    # 写入输出JSON文件
    with open(output_file_path, 'w', encoding='utf-8') as output_file:
        for entry in output_data:
            json_line = json.dumps(entry, ensure_ascii=False)
            output_file.write(json_line + '\n')

    print(f"转换完成，结果已写入 {output_file_path}")


# Example usage
input_json_path = "F:\\digital_man\\datasets\\travel_data\\525_0806_train.json"
output_json_path = "F:\\digital_man\\datasets\\travel_data\\converted_zhipu_nishuone028_train.json"

convert_format_glm3(input_json_path, output_json_path)


# input_file = 'F:\\digital_man\\datasets\\travel_data\\525_0806_train.json'
# output_file = 'F:\\digital_man\\datasets\\travel_data\\converted_525_0806_train.json'
# convert_format_swift(input_file, output_file)