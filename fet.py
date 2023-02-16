#!/usr/bin/env python
# coding: utf-8

import atexit
import sys
import pandas as pd
import numpy as np
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import time
import ta 
import warnings
warnings.simplefilter("ignore")


# Variables
SYMBOL = "FETUSDT"
INTERVAL = "4h"
K_ENTER = 0.25
K_EXIT = 0.9
D_DIFF = 0.06
RSI_WINDOW = 14
STOCH_SMA = 3
REWARD = 1.1
RISK = 0.95


def exit_handler():
    print('My application is ending!')
    sys.stdout = orig_stdout
    f.close()

atexit.register(exit_handler)
orig_stdout = sys.stdout
f = open('fet_long.txt', 'w')
sys.stdout = f


# In[1]::
load_dotenv()


# In[2]:


#Loading my Bybit's API keys from the dotenv file
api_key_pw = os.getenv('api_key_bot_IP')
api_secret_pw = os.getenv('api_secret_bot_IP')
sender_pass = os.getenv('mail_key')
receiver_address = os.getenv('mail')

# In[3]:


#Establishing Connection with the API (SPOT)
from pybit import spot
session_auth = spot.HTTP(
    endpoint='https://api.bybit.com',
    api_key = api_key_pw,
    api_secret= api_secret_pw
)


# In[4]:


#This function gets Real ETH Price Data and creates a smooth dataframe that refreshes every 5 minutes
def get5minutedata():
    frame = pd.DataFrame(session_auth.query_kline(symbol=SYMBOL, interval=INTERVAL)["result"])
    frame = frame.iloc[:,: 6]
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    frame = frame.set_index("Time")
    frame.index = pd.to_datetime(frame.index, unit="ms")
    frame = frame.astype(float)
    return frame


# In[5]:


#Function to apply some technical indicators from the ta library
def apply_technicals(df):
    df["K"] = ta.momentum.stochrsi(df.Close, window= RSI_WINDOW)
    df["D"] = df["K"].rolling(STOCH_SMA).mean()
    df["RSI"] = ta.momentum.rsi(df.Close, window = RSI_WINDOW)
    df.dropna(inplace=True)


# In[7]:


class Signals:
    def __init__(self, df, lags):
        self.df = df
        self.lags = lags
    
    #Checking if we have a trigger in the last n time steps
    def get_trigger(self):
        df_2 = pd.DataFrame()
        for i in range(self.lags + 1):
            mask = (self.df["K"].shift(i) < K_ENTER)
            df_2 = df_2.append(mask, ignore_index = True)
        return df_2.sum(axis= 0)
    
    # Is the trigger fulfilled and are all buying conditions fulfilled?
    def decide(self):
         self.df["trigger"] = np.where(self.get_trigger(), 1, 0)
         self.df["Buy"]= np.where((self.df.trigger) &
                                   (self.df["K"] > self.df["D"] + D_DIFF), 1, 0)

# In[6]:


#The sender mail address and password
sender_address = 'pythontradingbot11@gmail.com'

#Function to automate mails
def send_email(subject, result = None, buy_price = None, exit_price = None, stop = None):
    content = ""
    if result is not None:
        content += f"Result: {result}\n"
    if buy_price is not None:
        content += f"Buy Price: {buy_price}\n"
    if exit_price is not None:
        content += f"TP Price: {exit_price}\n"
    if stop is not None:
        content += f"SL Price: {stop}\n"

    message = MIMEMultipart()
    message['From'] = sender_address
    message['To'] = receiver_address
    message['Subject'] = subject 
    message.attach(MIMEText(content, 'plain'))
    
    #Create SMTP session for sending the mail
    session_mail = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
    session_mail.starttls()  # enable security
    session_mail.login(sender_address, sender_pass)
    text = message.as_string()
    session_mail.sendmail(sender_address, receiver_address, text)
    session_mail.quit()


# In[7]:

def strategy_long(qty, open_position = False):
    df= get5minutedata()
    apply_technicals(df)
    inst = Signals(df, 0)
    inst.decide()
    print(f'Current Time is ' + str(df.index[-1]))
    print(f'Current Close is '+str(df.Close.iloc[-1]))
    print(f"RSI: {round(df.RSI.iloc[-1], 2)}    K: {round(df.K.iloc[-1], 2)}    D: {round(df.D.iloc[-1], 2)}")
    print("-----------------------------------------")

    if df.Buy.iloc[-1]:
        price = round(df.Close.iloc[-1],2)
        tp = round(price * REWARD,2)
        sl = round(price * RISK,2)
        send_email(subject = f"{SYMBOL} Open Long Order", buy_price=price, exit_price=tp, stop=sl)

        print("-----------------------------------------")

        print(f"Buyprice: {price}")

        print("-----------------------------------------")

        open_position=True
        
        
    while open_position:
        time.sleep(30)
        df = get5minutedata()
        apply_technicals(df)
        current_price = round(df.Close.iloc[-1], 2)
        current_profit = round((current_price-price) * qty, 2)
        K = round(df.K.iloc[-1], 2)
        D = round(df.D.iloc[-1], 2)
        print(f'Current Time is ' + str(df.index[-1]))
        print(f"Buyprice: {price}" + '             Close: ' + str(df.Close.iloc[-1]))
        print(f'Target: ' + str(tp) + "                Stop: " + str(sl))
        print(f"RSI: {round(df.RSI.iloc[-1], 2)}    K: {K}    D: {D}")
        print(f'K Target: {K_EXIT}')
        print(f'Current Profit : {current_profit}')
        print("-----------------------------------------------------")

        if current_price <= sl: 
            result = round((sl - price) * qty,2)
            print("Closed Position")
            send_email(subject=f"{SYMBOL} Long SL", result = result, buy_price=price, stop= sl)
            open_position = False
            exit()
        
        elif current_price >= tp:
            result= round((tp - price) * qty, 2)
            print("Closed Position")
            send_email(subject =f"{SYMBOL} Long TP", result = result, buy_price=price, exit_price= tp)
            open_position = False
            break

        elif K >= K_EXIT:
            K_exit_price = round(df.Close.iloc[-1], 2)
            result= round((K_exit_price - price) * qty, 2)
            print("Closed Position")
            send_email(subject =f"{SYMBOL} Long Closed - K >= {K_EXIT}", result = result, buy_price=price, exit_price= K_exit_price)
            open_position = False
            break



# In[8]:


while True: 
    strategy_long(3.5)
    time.sleep(60)