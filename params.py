#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 25 20:40:08 2017

@author: imonahov
"""

def load_config(config):
    global conf
    conf = config
    global random_scale
    random_scale = 0.00001 # Defines standard deviation for random Q values 
    global start_balance
    start_balance = 1.0
    global short
    short = False # Short calculation is currently incorrect hense disabled
    global actions
    actions = 2 # Number of actions (% of stock holdings) 2 for long only, 3 to add short
    # α ∈ [0, 1] (alpha) is the learning rate used to vary the weight given to new experiences compared with past Q-values.
    global alpha
    alpha = 0.2
    # γ ∈ [0, 1] (gamma) is the discount factor used to progressively reduce the value of future rewards. Best: 0.9
    global gamma
    gamma = 0.9
    # Probability to chose random action instead of best action from Q Table. Best values: 0.2 - 0.5
    global epsilon
    epsilon = 0.5
    global train
    train = False # Train model
    global reload
    reload = False # Force to reload price data  
    global charts
    charts = False # Plot charts
    global stats
    stats = True # Show model stats
    global epochs
    epochs = 100 # Number of iterations for training (best 50)
    global features
    features = 4 # Number of features in state for Q table
    global feature_bins
    feature_bins = 3 # Number of bins for feature (more bins tend to overfit)
    global gdax_api
    gdax_api = ''
    global gdax_secret
    gdax_secret = ''
    global gdax_pass
    gdax_pass = ''
    global max_r
    max_r = 0
    global ticker
    ticker = conf[0:3]
    global currency
    currency = conf[3:6]
    global cfgdir
    cfgdir = 'data/'+conf
    global version
    version = 2 # Model version
    global sma_period
    sma_period = 50 # Best: 50
    global adr_period
    adr_period = 20 # Average Daily Return period
    global hh_period
    hh_period = 50 # Window for Highest High (best: 20 - 50)
    global ll_period
    ll_period = 50 # Window for Lowest Low (best: 20 - 50)
    global rsi_period
    rsi_period = 50
    global exchange
    exchange = 'CCCAGG' # Average price from all exchanges
    global execute
    execute = False
    global order_size
    order_size = 0 # Maximum order size in equity
    global result_size
    result_size = 0
    global order_wait
    order_wait = 10
    global min_cash
    min_cash = 1
    global min_equity
    min_equity = 0.001
    global bar_period
    bar_period = 'day' # Price bar period: day or hour
    global max_bars
    max_bars = 0 # Number of bars to use for training
    global train_goal
    train_goal = 'R' # Maximize Return
    global spread
    spread = 0.004 # Bitfinex fee
    global ratio
    ratio = 0 # Min ratio for Q table to take an action
    global shuffle
    shuffle = False
    global units
    units = 16
    global train_pct
    train_pct = 0.8 # % of data used for training
    global test_pct
    test_pct = 0.2 # % of data used for testing
    global model
    model = ''
    global plot_bars # Number of bars to plot. 0 means plot all
    plot_bars = 30
    global adj_strategy # Use adjusted strategy - with Cash signal
    adj_strategy = True

    if conf == 'BTCUSD': # R: 180.23 SR: 0.180 QL/BH R: 6.79 QL/BH SR: 1.80
#        train = True
        max_r = 18
        version = 1
    elif conf == 'ETHUSD': # R: 6984.42 SR: 0.164 QL/BH R: 8.94 QL/BH SR: 1.30
#        6508 / 1.25
        max_r = 6984
    elif conf == 'ETHBTC': # R: 1020.86 SR: 0.148 QL/BH R: 36.71 QL/BH SR: 1.81
        # 918 / 1.29
        version = 1
        max_r = 1020
    elif conf == 'ETHUSDNN': # 26955 / 2.20
#        train = True
#        plot_bars = 200
        stats = True
        charts = True
        short = True
        model = cfgdir+'/model65.nn'
    elif conf == 'BTCUSDNN': # Strategy Return: 18.39
#        train = True
        short = True
        units = 32
        sma_period = 15
        hh_period = 20
        ll_period = 20
        rsi_period = 5
        model = cfgdir+'/model57.nn'
    elif conf == 'ETHBTCNN': # 847 / 2.26
#        train = True
        units = 10
        sma_period = 15
        hh_period = 20
        ll_period = 20
        rsi_period = 15
        model = cfgdir+'/model62.nn'
    elif conf == 'DIGUSDNN':
#        train = True
        units = 10
        model = cfgdir+'/model77.nn'
        
    if train:
        charts = True
        stats = True
    else:
        test_pct = 1 # This is required for Adjusted Strategy stats calculation
        
    global file
    file = cfgdir+'/price.pkl'
    global q
    q = cfgdir+'/q.pkl'
    global tl
    tl = cfgdir+'/tl.pkl'
    print('')
    print('**************** Loaded Config for '+conf+' ****************')

#load_config('')