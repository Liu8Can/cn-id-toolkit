import json
import datetime
from collections import defaultdict
import time

class IDCardToolkit:
    """
    一个功能强大的中国公民身份号码工具集 (v5.0 - 最终版).
    核心原则: 控制台摘要 + 文件报告分离.
    1. 解析与验证
    2. 逆向推导/猜测
    3. 人口数据挖掘 (生成详细报告文件)
    4. 独立验证
    """

    def __init__(self, json_path='pca-code.json'):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.pca_data = json.load(f)
            self.area_codes = self._flatten_codes(self.pca_data)
        except FileNotFoundError:
            print(f"错误：未找到行政区划文件 '{json_path}'。请确保文件存在于同目录下。")
            self.area_codes = {}
        
        self.WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        self.CHECKSUM_MAP = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']

    def _flatten_codes(self, data, parent_name='', result=None):
        if result is None: result = {}
        for item in data:
            code, current_full_name = item['code'], parent_name + item['name']
            result[code] = current_full_name
            if 'children' in item:
                self._flatten_codes(item['children'], current_full_name, result)
        return result

    def _calculate_checksum(self, id_prefix: str) -> str:
        if not (isinstance(id_prefix, str) and len(id_prefix) == 17 and id_prefix.isdigit()):
            raise ValueError("输入必须是17位数字字符串")
        total = sum(int(digit) * weight for digit, weight in zip(id_prefix, self.WEIGHTS))
        return self.CHECKSUM_MAP[total % 11]

    def validate(self, id_number: str) -> tuple[bool, str]:
        id_number = id_number.strip().upper()
        if not (isinstance(id_number, str) and len(id_number) == 18):
            return False, "长度错误：必须为18位"
        prefix = id_number[:-1]
        if not prefix.isdigit():
            return False, "格式错误：前17位必须是数字"
        last_char = id_number[-1]
        if not (last_char.isdigit() or last_char == 'X'):
            return False, "格式错误：最后一位必须是数字或'X'"
        area_code = id_number[:6]
        if area_code not in self.area_codes:
            return False, f"地址码错误：无效的行政区划代码 {area_code}"
        birth_date_str = id_number[6:14]
        try:
            birth_date = datetime.datetime.strptime(birth_date_str, "%Y%m%d")
            if birth_date > datetime.datetime.now():
                return False, f"日期错误：出生日期不能是未来日期 {birth_date_str}"
        except ValueError:
            return False, f"日期错误：无效的出生日期格式 {birth_date_str}"
        try:
            expected_checksum = self._calculate_checksum(prefix)
            if last_char != expected_checksum:
                return False, f"校验码错误：计算值应为 '{expected_checksum}'，提供值为 '{last_char}'"
        except ValueError:
            return False, "内部计算错误"
        return True, "身份证号码有效"

    def parse(self, id_number: str) -> dict:
        is_valid, message = self.validate(id_number)
        if not is_valid: return {"valid": False, "error": message}
        area_code, birth_date_str = id_number[:6], id_number[6:14]
        province_code, city_code = area_code[:2], area_code[:4]
        birth_date = datetime.datetime.strptime(birth_date_str, "%Y%m%d")
        today = datetime.date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        seq_code, gender = int(id_number[14:17]), "男 (Male)" if int(id_number[16]) % 2 != 0 else "女 (Female)"
        return {"valid": True, "address_code": area_code, "address_info": {"province": self.area_codes.get(province_code, f"未知省份({province_code})"), "city": self.area_codes.get(city_code, f"未知城市({city_code})"), "district": self.area_codes.get(area_code, f"未知区县({area_code})")}, "birth_date": birth_date.strftime("%Y-%m-%d"), "age": age, "gender": gender, "sequence_code": id_number[14:17], "checksum": id_number[-1]}

    def guess(self, area_code: str, birth_date: str, gender: str) -> list:
        if area_code not in self.area_codes: return [f"错误: 无效或不存在的行政区划代码 {area_code}"]
        try: datetime.datetime.strptime(birth_date, "%Y%m%d")
        except ValueError: return [f"错误: 无效的出生日期格式 {birth_date} (应为 YYYYMMDD)"]
        gender = gender.upper()
        if gender not in ['M', 'F']: return ["错误: 性别必须是 'M' 或 'F'"]
        prefix_14, possible_ids = area_code + birth_date, []
        start = 1 if gender == 'M' else 2
        for i in range(start, 1000, 2):
            seq_code = f"{i:03d}"
            prefix_17 = prefix_14 + seq_code
            possible_ids.append(prefix_17 + self._calculate_checksum(prefix_17))
        return possible_ids

    def analyze_population_sample(self, id_list: list) -> dict:
        valid_ids, invalid_details = [], []
        for id_number in id_list:
            is_valid, message = self.validate(id_number)
            if is_valid: valid_ids.append(id_number)
            else: invalid_details.append({"号码": id_number, "错误原因": message})
        
        stats = defaultdict(lambda: {"male_seqs": [], "female_seqs": []})
        for id_number in valid_ids:
            key, seq = (id_number[:6], id_number[6:14]), int(id_number[14:17])
            if seq % 2 != 0: stats[key]["male_seqs"].append(seq)
            else: stats[key]["female_seqs"].append(seq)
        
        analysis_report = {}
        for key, data in stats.items():
            area_code, date_str = key
            area_name = self.area_codes.get(area_code, "未知地区")
            max_male_seq, max_female_seq = (max(data["male_seqs"]) if data["male_seqs"] else 0), (max(data["female_seqs"]) if data["female_seqs"] else 0)
            estimated_males, estimated_females = (max_male_seq + 1) // 2 if max_male_seq > 0 else 0, max_female_seq // 2 if max_female_seq > 0 else 0
            analysis_report[f"{area_name} ({date_str})"] = {"有效样本数量": len(data["male_seqs"]) + len(data["female_seqs"]), "估算男性登记数": estimated_males, "估算女性登记数": estimated_females, "估算总登记数": estimated_males + estimated_females, "备注": "基于样本中最大顺序码的统计估算，非精确值。"}
        
        return {
            "summary": {"total_records": len(id_list), "valid_records": len(valid_ids), "invalid_records": len(invalid_details)},
            "analysis_report": analysis_report,
            "invalid_details": invalid_details
        }

def main_cli():
    try:
        toolkit = IDCardToolkit()
        if not toolkit.area_codes: return
    except Exception as e:
        print(f"初始化工具失败: {e}")
        return

    while True:
        print("\n===== 中国公民身份号码极客工具箱 (v5.0) =====")
        print("1. [解析] - 解析单个身份证号码")
        print("2. [猜测] - 根据信息生成所有可能的号码")
        print("3. [分析] - 从文件读取号码列表并生成分析报告")
        print("4. [验证] - 快速验证单个号码的有效性")
        print("5. [退出] - 退出程序")
        choice = input("请输入您的选择 (1-5): ")

        if choice == '1':
            id_num = input("请输入18位身份证号码: ")
            result = toolkit.parse(id_num)
            print("--- 解析结果 ---"); [print(f"{k}: {v}" if not isinstance(v, dict) else f"{k}:\n" + "".join([f"  {sk}: {sv}\n" for sk, sv in v.items()]), end='') for k, v in result.items()]; print("------------------")

        elif choice == '2':
            print("--- 逆向猜测工具 ---")
            area_code, birth_date, gender = input("请输入6位行政区划代码: "), input("请输入8位出生日期 (YYYYMMDD): "), input("请输入性别 ('M'男/'F'女): ")
            results = toolkit.guess(area_code, birth_date, gender)
            if results and "错误" in results[0]: print(results[0])
            else:
                print(f"已成功生成 {len(results)} 个可能的号码。")
                if input("是否将结果保存到文件? (y/n): ").lower() == 'y':
                    filename = f"guess_{area_code}_{birth_date}_{gender.upper()}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
                    try:
                        with open(filename, 'w') as f: f.write('\n'.join(results))
                        print(f"结果已成功保存到文件: {filename}")
                    except IOError as e: print(f"文件保存失败: {e}")
            print("------------------")

        elif choice == '3':
            print("--- 批量分析工具 ---")
            filename = input("请输入包含身份证号码列表的文件名 (默认为 id_list.txt): ").strip() or "id_list.txt"
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    id_list = [line.strip() for line in f if line.strip()]
                if not id_list:
                    print(f"文件 '{filename}' 为空或不包含有效行。")
                    continue

                full_result = toolkit.analyze_population_sample(id_list)
                summary, report_data, invalid_data = full_result["summary"], full_result["analysis_report"], full_result["invalid_details"]
                
                # 1. 控制台输出简洁摘要
                print("\n--- 分析摘要 ---")
                print(f"共处理 {summary['total_records']} 条记录。")
                print(f"  - ✔️ 有效记录: {summary['valid_records']} 条")
                print(f"  - ❌ 无效记录: {summary['invalid_records']} 条")

                # 2. 生成详细报告文件
                report_filename = f"report_{filename.replace('.', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
                with open(report_filename, 'w', encoding='utf-8') as f:
                    f.write("身份证号码批量分析报告\n")
                    f.write(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"数据源文件: {filename}\n")
                    f.write("="*50 + "\n\n")

                    f.write("【1. 分析摘要】\n")
                    f.write(f"  - 总计处理记录: {summary['total_records']} 条\n")
                    f.write(f"  - 有效记录数量: {summary['valid_records']} 条\n")
                    f.write(f"  - 无效记录数量: {summary['invalid_records']} 条\n\n")

                    f.write("【2. 人口估算统计报告】\n")
                    if report_data:
                        for key, data in report_data.items():
                            f.write(f"\n  分析对象: {key}\n")
                            for sub_key, val in data.items():
                                f.write(f"    - {sub_key}: {val}\n")
                    else:
                        f.write("  在提供的列表中未找到任何有效的身份证号码进行分析。\n")
                    f.write("\n" + "="*50 + "\n\n")

                    f.write("【3. 无效记录详情】\n")
                    if invalid_data:
                        for item in invalid_data:
                            f.write(f"  - 号码: {item['号码']:<20} | 原因: {item['错误原因']}\n")
                    else:
                        f.write("  所有记录均有效，无无效记录。\n")
                
                print(f"\n✅ 详细分析报告已生成: {report_filename}")

            except FileNotFoundError:
                print(f"错误：文件 '{filename}' 未找到。请确保文件与脚本在同一目录下。")
            
        elif choice == '4':
            id_num = input("请输入18位身份证号码进行验证: ")
            is_valid, message = toolkit.validate(id_num)
            print("--- 验证结果 ---"); print(f"有效性: {'✔ 有效' if is_valid else '❌ 无效'}\n原因: {message}"); print("------------------")

        elif choice == '5':
            print("感谢使用，再见！")
            break
        else:
            print("无效输入，请输入1到5之间的数字。")

if __name__ == "__main__":
    main_cli()