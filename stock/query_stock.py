import pandas as pd
import re

class StockSearcher:
    def __init__(self, csv_file):
        """
        初始化股票搜索器
        :param csv_file: CSV文件路径
        """
        self.df = pd.read_csv(csv_file)
        print(f"成功加载数据，共 {len(self.df)} 条记录")
        print("可用字段:", list(self.df.columns))
    
    def fuzzy_search(self, keyword, search_fields=None):
        """
        模糊搜索股票信息
        :param keyword: 搜索关键词
        :param search_fields: 搜索字段列表，为None时搜索所有字段
        :return: 匹配的DataFrame
        """
        if search_fields is None:
            search_fields = self.df.columns.tolist()
        
        # 确保搜索字段存在
        valid_fields = [field for field in search_fields if field in self.df.columns]
        if not valid_fields:
            print("错误：指定的搜索字段不存在")
            return pd.DataFrame()
        
        # 创建匹配掩码
        mask = pd.Series([False] * len(self.df))
        
        for field in valid_fields:
            # 使用正则表达式进行模糊匹配（不区分大小写）
            field_mask = self.df[field].astype(str).str.contains(
                re.escape(keyword), case=False, na=False, regex=True
            )
            mask = mask | field_mask
        
        results = self.df[mask].copy()
        return results
    
    def search_and_display(self, keyword, search_fields=None, max_display=10):
        """
        搜索并显示结果
        """
        results = self.fuzzy_search(keyword, search_fields)
        
        if len(results) == 0:
            print(f"未找到包含 '{keyword}' 的记录")
            return
        
        print(f"\n找到 {len(results)} 条包含 '{keyword}' 的记录:")
        print("=" * 100)
        
        # 显示前max_display条记录
        display_results = results.head(max_display)
        
        for idx, row in display_results.iterrows():
            print(f"\n记录 {idx + 1}:")
            for col in self.df.columns:
                print(f"  {col}: {row[col]}")
            print("-" * 50)
        
        if len(results) > max_display:
            print(f"\n... 还有 {len(results) - max_display} 条记录未显示")
        
        return results

def main():
    # 使用示例
    csv_file = "data/tushare_stock_basic_20251118214156.csv"  # 替换为您的CSV文件路径
    
    try:
        searcher = StockSearcher(csv_file)
    except FileNotFoundError:
        print(f"错误：找不到文件 {csv_file}")
        return
    except Exception as e:
        print(f"加载文件时出错: {e}")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("股票信息查询系统")
        print("=" * 50)
        print("1. 全字段搜索")
        print("2. 指定字段搜索")
        print("3. 显示所有字段")
        print("4. 退出")
        
        choice = input("\n请选择操作 (1-4): ").strip()
        
        if choice == '1':
            keyword = input("请输入搜索关键词: ").strip()
            if keyword:
                searcher.search_and_display(keyword)
            else:
                print("关键词不能为空")
                
        elif choice == '2':
            print("可用字段:", list(searcher.df.columns))
            fields_input = input("请输入要搜索的字段（多个字段用逗号分隔）: ").strip()
            keyword = input("请输入搜索关键词: ").strip()
            
            if fields_input and keyword:
                search_fields = [field.strip() for field in fields_input.split(',')]
                searcher.search_and_display(keyword, search_fields)
            else:
                print("字段和关键词都不能为空")
                
        elif choice == '3':
            print("\n所有字段说明:")
            for i, col in enumerate(searcher.df.columns, 1):
                print(f"{i}. {col}: {searcher.df[col].iloc[0] if len(searcher.df) > 0 else '无数据'}")
                
        elif choice == '4':
            print("谢谢使用！")
            break
        else:
            print("无效选择，请重新输入")

# 简化版本 - 如果只需要基本功能
def simple_search(csv_file, keyword, search_fields=None):
    """
    简化版搜索函数
    """
    df = pd.read_csv(csv_file)
    
    if search_fields is None:
        search_fields = df.columns.tolist()
    
    mask = pd.Series([False] * len(df))
    for field in search_fields:
        if field in df.columns:
            field_mask = df[field].astype(str).str.contains(keyword, case=False, na=False)
            mask = mask | field_mask
    
    results = df[mask]
    
    if len(results) > 0:
        print(f"找到 {len(results)} 条记录:")
        print(results.to_string(index=False))
    else:
        print("未找到匹配的记录")
    
    return results

if __name__ == "__main__":
    # 安装依赖（如果尚未安装）
    try:
        import pandas as pd
    except ImportError:
        print("请先安装pandas: pip install pandas")
        exit()
    
    main()