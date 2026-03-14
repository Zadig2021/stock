import tushare as ts
import pandas as pd

# 1. 设置你的Tushare Pro Token
ts.set_token('d247b4819e87e05555d896c78c41b0fd5dfd26e8bd24ebcc6103d782') 
pro = ts.pro_api()

pro = ts.pro_api()

#获取浦发银行60000.SH的历史分钟数据
df = pro.stk_mins(ts_code='603260.SH', freq='1min', start_date='2025-11-26 09:00:00', end_date='2025-11-2 19:00:00')
print(df)