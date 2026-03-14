#!/usr/bin/python
# -*- coding: UTF-8 -*-

from jqdatasdk import *
from strategy import *
from store import *

# jqdata user
user = '15651368958'
# password
password = 'Hander012'
# quote end date
endDate = '2025-11-14 15:00:00'
# test cycle
cycle = 5
# buy size and buy basket
buySize = 0
basket=[]

# judge whether the stock will raise in next period
def judgeStockRaise(stock, cycle, endDate):
    """judge whether the stock will raise in next period"""
    df = get_price(stock, end_date=endDate, frequency='daily', count=cycle + 1)
    #print(df)
    if len(df) < cycle + 1:
        return False
    startPrice = df['close'][0]
    endPrice = df['close'][cycle]
    change = (endPrice - startPrice) / startPrice
    #print("stock:", stock, " change:", change)
    if change >= 0.1:
        return True
    return False

# get all stock list from jqdata
# 获取所有股票列表、名称
def getAllStockList():
    """get all stock list from jqdata"""
    stocks = get_all_securities(types=['stock'], date='2025-11-16').index.tolist()
    return stocks

# write stock list to file
def writeStockListToFile(filename, stocks):
    """write stock list to file"""
    with open(filename, 'w') as f:
        for item in stocks.index:
            # print(item)
            f.write(str(item) + '\n')

# saveStockListToFile
def saveStockListToFile():
    writeStockListToFile('stocklist.txt', getAllStockList())

def runMain():
    # 账号登录
    auth(user, password)
    
    # 打印账号信息
    # infos = get_account_info()
    # print(infos)

    # 下载股票代码列表
    saveStockListToFile()

    # 股票
    # 601012.XSHG
    # 000001.XSHE
    # stock = get_security_info('601012.XSHG')
    # print("上市日期:", stock.start_date)

    # 期货合约
    # futu_list = get_future_contracts('AU','2025-01-05')
    # print(futu_list)

    # futu = get_security_info('AU2501.XSGE', date='2025-01-05')
    # print("futu:", futu.start_price)

    logout()

runMain()