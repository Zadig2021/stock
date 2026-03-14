import akshare as ak

# 注意：该接口返回的数据只有最近一个交易日的有开盘价，其他日期开盘价为 0
symbol = "603260"  # 合盛硅业股票分钟K线
name = "合盛硅业"
date = "2025-11-27"
stock_zh_a_hist_min_em_df = ak.stock_zh_a_hist_min_em(symbol=symbol, start_date=f"{date} 09:30:00", end_date=f"{date} 15:00:00", period="1", adjust="")
# print(stock_zh_a_hist_min_em_df)
with open(f'{symbol}_{date}_minute_data.csv', 'a') as f:
    f.write("时间,开盘,最高,最低,收盘,成交量,成交额\n")
    for index, row in stock_zh_a_hist_min_em_df.iterrows():
        f.write(f"{row['时间']},{row['开盘']},{row['最高']},{row['最低']},{row['收盘']},{row['成交量']},{row['成交额']}\n")