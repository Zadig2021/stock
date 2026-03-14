import akshare as ak

symbol = "sh601012"  # 合盛硅业股票逐笔成交数据

stock_zh_a_tick_tx_js_df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
with open(f'{symbol}_tick_data.csv', 'a') as f:
    f.write("成交时间,成交价格,价格变动,成交量,成交金额,性质\n")
    for index, row in stock_zh_a_tick_tx_js_df.iterrows():
        f.write(f"{row['成交时间']},{row['成交价格']},{row['价格变动']},{row['成交量']},{row['成交金额']},{row['性质']}\n")