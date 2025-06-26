import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import ast

# 🛠️ 텔레그램 설정 (GitHub Secrets로 주입)
import os
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def fetch_price_data(code):
    # 네이버 금융에서 한국 주식 가격 크롤링 (10일치)
    url = f"https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime=20230101&endTime=99991231&timeframe=day"
    headers = {
        "Referer": "https://finance.naver.com",
        "User-Agent": "Mozilla/5.0"
    }
    res = requests.get(url, headers=headers)
    # print(f"{code} 원본 응답:\n{res.text[:200]}")
    
    data_str = res.text.strip()
        
    if not data_str or data_str == '[]':
        print(f"{code} 빈 데이터 또는 응답 없음")
        return None
       
    try:
        data = ast.literal_eval(data_str)
    except Exception as e:
        print(f"{code} 데이터 파싱 오류: {e}")
        return None
        
    df = pd.DataFrame(data[1:], columns=data[0])
    df = df.rename(columns={'날짜': 'date', '종가': 'close', '시가': 'open'})
    df = df[['date', 'open', 'close']].copy()
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df = df.dropna()
    df.reset_index(drop=True, inplace=True)
    return df

def get_stock_name(code):
    url = f"https://finance.naver.com/item/main.nhn?code={code}"
    res = requests.get(url)
    import re
    m = re.search(r'<title>(.+?) : 네이버 금융</title>', res.text)
    if m:
        return m.group(1)
    return code

def analyze_stock(code):
    try:
        df = fetch_price_data(code)
        if len(df) < 7:
            return None  # insufficient data

        df['ma5'] = df['close'].rolling(window=5).mean()
        df = df.dropna()

        day0 = df.iloc[-1]
        day1 = df.iloc[-2]
        day2 = df.iloc[-3]

        기준1 = day1['ma5'] * 0.983  # 전일
        기준2 = day2['ma5'] * 0.983  # 2일전

        if day1['close'] < 기준2 and day0['open'] > 기준1:
            return {
                'code': code,
                'name': name,
                'day0_open': round(day0['open'], 2),
                'day1_close': round(day1['close'], 2),
                '기준1': round(기준1, 2),
                '기준2': round(기준2, 2),
            }
    except Exception as e:
        print(f"{code} 분석 중 오류: {e}")
    return None

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    res = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })
    print(f"[텔레그램 전송됨]: {msg}")

def main():
    with open("symbols.json", "r") as f:
        codes = json.load(f)

    results = []
    for code in codes:
        result = analyze_stock(code)
        if result:
            results.append(result)

    if results:
        msg = f"[📈 조건 충족 종목 알림 - {datetime.now().strftime('%Y-%m-%d %H:%M')}]\n"
        for r in results:
            msg += f"\n🟢 {r['name']} ({r['code']})\n"
            msg += f" - 어제 MA5-1.7%: {r['기준1']}\n"
            msg += f" - 2일전 MA5-1.7%: {r['기준2']}\n"
            msg += f" - 전일 종가: {r['day1_close']}\n"
            msg += f" - 오늘 시가: {r['day0_open']}\n"
        send_telegram(msg)
    else:
        print("조건에 맞는 종목 없음.")

if __name__ == "__main__":
    main()
