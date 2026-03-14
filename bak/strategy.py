#!/usr/bin/python
# -*- coding: UTF-8 -*-
from jqdatasdk import *

def judgeStockRaise(stock, count, endDate):
    #print(stock)
    #print(endDate)
    df = get_price(stock, end_date=endDate, count=count, frequency='daily', fields=['open','close','high','low','volume','money'])
    #print(df['open'])
    open = df['open']
    close = df['close']
    high = df['high']
    low = df['low']
    buy = True
    for i in range(1, count):
        if open[i] < open[i-1] or close[i] < close[i-1] or open[i] > close[i]:
            buy = False
            break

    return buy

def judgeStockStar(stock, count, endDate):
    #print(stock)
    df = get_price(stock, end_date=endDate, count=count, frequency='daily', fields=['open','close','high','low','volume','money'])
    #print(df['open'])
    open = df['open']
    close = df['close']
    high = df['high']
    low = df['low']
    buy = False
    for i in range(count):
        if abs(open[i] - close[i])/close[i] < 0.005 and abs(high[i] - low[i]) / close[i] > 0.03:
            buy = True
            break

    return buy

def judgeStockV(stock, count, endDate):
   #print(stock)
    df = get_price(stock, end_date=endDate, count=count, frequency='daily', fields=['open','close','high','low','volume','money'])
    #print(df['open'])
    open = df['open']
    close = df['close']
    high = df['high']
    low = df['low']
    buy = False
    for i in range(1,count-1):
        if abs(open[i] - close[i])/close[i] < 0.005 and abs(high[i] - low[i]) / close[i] > 0.03:
            buy = True

            for j in range(i) :
                if close[j] < close[j+1]:
                    buy = False
                    break

            if buy == False :
                continue

            for j in range(i+1,count) :
                if close[j-1] > close[j] :
                    buy = False
                    break

            if buy:
                break

    return buy