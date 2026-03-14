ps x | grep real_trading_main | grep -v grep | awk -F ' ' '{print $1}' | xargs kill -9
