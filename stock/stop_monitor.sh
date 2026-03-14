ps x | grep monitor | grep -v grep | awk -F ' ' '{print }' | xargs kill
