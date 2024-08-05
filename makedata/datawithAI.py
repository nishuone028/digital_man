from copy import deepcopy
from pathlib import Path
from http import HTTPStatus
from dashscope import Generation
from tqdm import tqdm
import yaml
import dashscope
import json
import os
import random
import re
import requests
from zhipuai import ZhipuAI
import argparse


def set_api_key(api_model_name, api_yaml_path):
    """
    设置 api key
    Args:
        api_model_name (str): api 类型
        api_yaml_path (str): api yaml 文件路径
    """
    with open(api_yaml_path, "r", encoding="utf-8") as f:
        api_yaml = yaml.safe_load(f)

    if api_model_name == 'qwen':
        api_key = api_yaml['ali_qwen_api_key']
        dashscope.api_key = api_key

    elif api_model_name == 'baichuan':
        api_key = api_yaml['baichuan_api_key']

    elif api_model_name == 'zhipu':
        api_key = api_yaml['zhipu_api_key']

    else:
        raise ValueError("api_type must be qwen or ernie or zhipu!!")

    return api_key


def call_api(content_str, model_name, api_key, model_type=dashscope.Generation.Models.qwen_turbo):
    """
    Calls the Qwen or Ernie API and handles retries.

    Args:
        content_str (str): The content string to send.
        model_name (str): The name of the model ('qwen' or 'ernie').
        api_key (str): The API key to use for the API.
        model_type (str): The model type to use for Qwen.

    Returns:
        str: The raw text response from the API.
    """
    if model_name == 'qwen':
        dashscope.api_key = api_key
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = Generation.call(model_type, prompt=content_str)
                if response.status_code == HTTPStatus.OK:
                    return response.output.text
                else:
                    print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
                        response.request_id, response.status_code,
                        response.code, response.message
                    ))
            except Exception as e:
                if attempt < max_retries - 1:  # If it's not the last attempt
                    print(f"Attempt {attempt + 1} failed, retrying: {e}")
                else:
                    raise e
    elif model_name == 'baichuan':
        # Assuming you have the access token available
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={api_key}"
        payload = json.dumps({
            "messages": [
                {"role": "user", "content": content_str}
            ],
            "disable_search": False,
            "enable_citation": False,
        })
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == HTTPStatus.OK:
            response_json = response.json()
            return response_json["result"]
        else:
            raise Exception(f"API request failed with status {response.status_code}")

    elif model_name == 'zhipu':
        client = ZhipuAI(api_key=api_key)
        response = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "user", "content": content_str}
            ],
            top_p=0.7,
            temperature=0.9,
            stream=False,
            max_tokens=5000,
        )
        return response.choices[0].message.content


def process_api_response(content_str, model_name, api_key, model_type=dashscope.Generation.Models.qwen_turbo):
    """
    Processes the API response and formats it into a JSON object.

    Args:
        content_str (str): The content string to send to the API.
        model_name (str): The name of the model ('qwen' or 'ernie').
        model_type (str): The model type to use for Qwen.

    Returns:
        dict: A JSON-formatted dictionary.
    """
    try:
        # Call the API and get the raw response
        raw_response = call_api(content_str, model_name, api_key, model_type)

        # Extract JSON content if present
        if "```json" in raw_response:
            json_content = re.findall(r"```json(.*)```", raw_response, flags=re.DOTALL)[0]
        else:
            json_content = raw_response

        # Replace problematic characters
        cleaned_json = json_content.replace("\\", "\\\\").replace("\n\n", "\n").replace("”", '"').replace("“", '"')

        # Further clean for Qwen-specific issues
        if model_name == 'qwen':
            output_start = cleaned_json.find('"output": "')
            if output_start != -1:
                output_end = cleaned_json.find("}", output_start + 1)
                if output_end != -1:
                    output_segment = cleaned_json[output_start + len('"output": "'): output_end - 10]
                    cleaned_json = cleaned_json[:output_start + len('"output": "')] + output_segment.replace('"',
                                                                                                             "'") + cleaned_json[
                                                                                                                    output_start + len(
                                                                                                                        '"output": "') + len(
                                                                                                                        output_segment):]

        # Parse the cleaned JSON content
        return json.loads(cleaned_json, strict=False)

    except Exception as e:
        # Log the error and return a default error response
        with open(f"error-{model_name}.log", "a+", encoding="utf-8") as f_error:
            f_error.write(f"Error: {str(e)}\n")
            f_error.flush()
        return {"Error": "Error"}


def makedataset(dastset_yaml_path, api_yaml_path, save_json_root, model_name, specific_name=""):
    """
    1.判断是否存在存放由AI生成数据的文件夹
    2.读取AI相关对话配置文件
    3.设置API接口
    4.读取JSON文件，有关数据
    5.
    """
    # 检查 save_json_root 是否已经是一个有效的目录路径
    if not os.path.exists(save_json_root):
        # 如果不存在，则将其转换为目录对象并创建目录
        os.makedirs(save_json_root)
    else:
        # 如果已经存在，则不需要进行任何操作
        pass

    with open(dastset_yaml_path, "r", encoding="utf-8") as f:
        dataset_yaml = yaml.safe_load(f)

    if specific_name != "":
        assert (
                specific_name in dataset_yaml["role_type"]
        ), f"{specific_name} not in dataset_yaml['role_type'] ({dataset_yaml['role_type']}), pls check dataset yaml!"

    api_key = set_api_key(model_name, api_yaml_path)

    data_gen_setting = dataset_yaml["data_generation_setting"]
    gen_num = data_gen_setting["each_tour_gen"]
    each_pick_highlight = data_gen_setting["each_pick_highlight"]
    each_pick_question = data_gen_setting["each_pick_question"]

    qwen_model_type = [dashscope.Generation.Models.qwen_max] * gen_num

    for role_type, role_character in dataset_yaml["role_type"].items():

        if specific_name != "" and role_type != specific_name:
            print(f"specific_name = {specific_name}, skipping for {role_type}")
            continue

        gen_json = dict()

        save_json_path = Path(save_json_root).joinpath(f"{model_name}_{role_type}_train.json")
        bk_json_path = Path(save_json_root).joinpath(f"{model_name}_{role_type}_train.json.bk")

        if save_json_path.exists():
            with open(save_json_path, "r", encoding="utf-8") as f:
                gen_json = json.load(f)

        if bk_json_path.exists():
            bk_json_path.unlink()

        list_attraction = [
            attraction_name
            for _, attractions in dataset_yaml["attraction_list"].items()
            for _, attraction_name_list in attractions.items()
            for attraction_name in attraction_name_list.keys()
        ]

        character = "、".join(role_character)

        pbar = tqdm(total=len(list_attraction))

        for _, attractions in dataset_yaml["attraction_list"].items():
            for _, attraction_name_list in attractions.items():
                for attraction, highlights in attraction_name_list.items():
                    pbar.set_description(attraction)

                    if attraction in gen_json:
                        # 跳过已经有的
                        pbar.update(1)
                        continue

                    gen_json.update({attraction: []})

                    for idx in range(gen_num):
                        # 随机抽取 ${each_pick_highlight} 个景点特点
                        if each_pick_highlight >= len(highlights):
                            # 超过打乱，增加随机性
                            random.shuffle(highlights)
                            highlight_str = "、".join(highlights)
                        else:
                            highlights_list = random.sample(highlights, each_pick_highlight)
                            highlight_str = "、".join(highlights_list)

                        # 随机抽取 ${each_pick_question} 个提问角度
                        if each_pick_question >= len(dataset_yaml["customer_question_type"]):
                            # 超过打乱，增加随机性
                            random.shuffle(dataset_yaml["customer_question_type"])
                            customer_question_str = "、".join(dataset_yaml["customer_question_type"])
                        else:
                            customer_question_type = random.sample(dataset_yaml["customer_question_type"],
                                                                   each_pick_question)
                            customer_question_str = "、".join(customer_question_type)

                        # 商品信息
                        attraction_info_str = dataset_yaml["attraction_info_struct"][0].replace("{name}", attraction)
                        attraction_info_str += dataset_yaml["attraction_info_struct"][1].replace("{highlights}",
                                                                                                 highlight_str)

                        content_str = (
                            data_gen_setting["dataset_gen_prompt"]
                            .replace("{role_type}", role_type)
                            .replace("{character}", character)
                            .replace("{attraction_info}", attraction_info_str)
                            .replace("{customer_question}", customer_question_str)
                            .replace("{each_conversation_qa}", str(data_gen_setting["each_conversation_qa"]))
                            .replace(
                                "{dataset_json_format}",
                                data_gen_setting["dataset_json_format"].replace("{attraction_info}",
                                                                                attraction_info_str),
                            )
                        )

                        print(f"\n Request [ {model_name} ] {idx + 1}/{gen_num} ==> {content_str} \n")
                        if model_name == "qwen":
                            format_json = process_api_response(content_str, model_name, api_key, qwen_model_type[idx])
                        elif model_name == "baichuan":
                            format_json = process_api_response(content_str, model_name, api_key)
                        elif model_name == "zhipu":
                            format_json = process_api_response(content_str, model_name, api_key)
                        else:
                            raise ValueError(f"model_name {model_name} not support")

                        if "conversation" in format_json and len(format_json["conversation"]) > 0:

                            # 第一个结果因为节省 token，需要将 system 和 input 放回去
                            conversation_setting = deepcopy(dataset_yaml["conversation_setting"])
                            system_str = (
                                conversation_setting["system"].replace("{role_type}", role_type).replace("{character}",
                                                                                                         character)
                            )
                            input_str = conversation_setting["first_input"].replace("{attraction_info}",
                                                                                    attraction_info_str)

                            # 将第一个对话加入必要信息
                            format_json["conversation"][0] = {
                                "system": system_str,
                                "input": input_str,
                                "output": format_json["conversation"][0]["output"],
                            }
                        else:
                            format_json = {"Error": "Error"}

                        print(f"\n Response [ {model_name} ] {idx + 1}/{gen_num} <== {format_json} \n")
                        gen_json[attraction].append(format_json)

                    pbar.update(1)

                    # 备份旧的
                    if save_json_path.exists():
                        save_json_path.rename(bk_json_path)

                    # 保存 json
                    with open(save_json_path, "w", encoding="utf-8") as f:
                        json.dump(gen_json, f, indent=4, ensure_ascii=False)

                    # 如果保存成功，删掉旧的
                    if bk_json_path.exists():
                        bk_json_path.unlink()


if __name__ == "__main__":
    # dastset_yaml_path = "F:\\digital_man\\config\\conversation_cfg.yaml"
    # api_yaml_path = "F:\\digital_man\\api\\api_cfg.yaml"
    # save_json_root = "gen_dataset"
    # model_name = "zhipu"
    # specific_name = "nishuone028"

    # 命令行输入参数
    parser = argparse.ArgumentParser(description="Make Dataset")
    parser.add_argument("--model_name", type=str, choices=["qwen", "ernie", "zhipu"], help="Model name for data "
                                                                                           "generation")
    parser.add_argument("--dastset_yaml_path", type=str, default="F:\\digital_man\\config\\conversation_cfg.yaml",
                        help="data setting file path")
    parser.add_argument("--api_yaml_path", type=str, default="F:\\digital_man\\api\\api_cfg.yaml", help="api setting "
                                                                                                        "file path")
    parser.add_argument("--save_json_root", type=str, default="gen_dataset", help="generation json output dir")
    parser.add_argument("--specific_name", type=str, default="nishuone028", help="Character name for data generation")
    args = parser.parse_args()

    makedataset(args.dastset_yaml_path, args.api_yaml_path, args.save_json_root, "zhipu", args.specific_name)
