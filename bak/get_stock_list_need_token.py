import tushare as ts
import pandas as pd

# 设置您的Tushare token（在Tushare官网注册后免费获取）
my_token = 'd247b4819e87e05555d896c78c41b0fd5dfd26e8bd24ebcc6103d782'
ts.set_token(my_token)
pro = ts.pro_api()

# 获取所有上市股票的基本信息列表
# 参数说明：exchange-交易所（SSE上交所, SZSE深交所, BSE北交所）， list_status-上市状态（L上市）
df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,list_date')

# 重命名列以便理解
df = df.rename(columns={'ts_code': '股票代码', 'symbol': '交易代码', 'name': '股票名称', 'list_date': '上市日期'})

# 查看前10行数据
print(df.head(10))

# 保存到CSV文件
df.to_csv('A股上市公司列表.csv', index=False, encoding='utf-8-sig')