#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 25 17:47:41 2018

@author: igor
"""

import nn
import tele as t
import exchange as x
import datetime as dt
import time
import params as p

def send(msg, public=False):
    print(msg)
    t.send_msg(str(msg), public)

def get_signal(conf):
    while True:
        nn.runNN(conf)
        signal = nn.get_signal()
        if dt.datetime.today() > signal['close_ts']:
            send('Signal has expired. Waiting for new one ...')
            time.sleep(p.sleep_interval)
        else:
            return signal

def send_results(res, msg):
    send(msg+' of '+str(res['size'])+' '+p.pair+' with price '+str(res['price']))

def execute(conf):
    s = get_signal(conf)
    s0 = nn.get_signal(-2)
 
    send(p.pair, True)
    # Send details about previous and current positions
    send('Yesterday: ' + nn.get_signal_str(s0), True)
    send('Today: ' + nn.get_signal_str(s), True)
    if p.execute:
        action = s['action']
        prev_action = s0['action']
        is_open = True
        # FIXME: triggering both SL and TP should be handled / avoided
        if not x.has_sl_order():
            is_open = False
            send('Stop Loss triggered!')
        
        if not x.has_tp_order():
            is_open = False
            send('Take Profit triggered!')
        
        # Update Stop Loss and Take Profit
        x.cancel_orders()
        if action == 'Buy':
            send(x.sl_order('Sell'))
            send(x.tp_order('Sell'))
        elif action == 'Sell' and p.short:
            send(x.sl_order('Buy'))
            send(x.tp_order('Buy'))
        
        # Close position if signal has changed and it is still open
        if is_open and s['new_signal'] and (p.short and prev_action == 'Sell' or prev_action == 'Buy'):
            res = x.close_position(prev_action)
            send_results(res, 'Closing '+prev_action+' Position')
            is_open = False
        
        if not is_open and (action == 'Buy' or action == 'Sell' and p.short):
            res = x.execute_order(action, wait=True)
            send_results(res, 'Opened '+action+' Position')

        if x.has_orders(): 
            send('Some orders are still open. Waiting ...')
            x.wait_orders()
            send('All orders have executed.')

        send('Balance: '+str(x.get_balance()))
            

def run_model(conf):
    try:
        execute(conf)
    except Exception as e:
        send('An error has occured. Please investigate!')
        send(e)
    
run_model('ETHUSDNN1')
t.cleanup()
