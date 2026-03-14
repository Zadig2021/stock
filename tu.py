import tushare as ts
import pandas as pd

# 1. 设置你的Tushare Pro Token
ts.set_token('d247b4819e87e05555d896c78c41b0fd5dfd26e8bd24ebcc6103d782') 
pro = ts.pro_api()

# 3. 获取逐笔数据
# 注意：这个接口可能需要一定的积分权限
df = ts.pro_bar(ts_code='300454.SZ', start_date='20251001', end_date='20251130', asset='E')
print(df)

# 数据列通常包括：时间、价格、成交量、成交额、买卖方向等