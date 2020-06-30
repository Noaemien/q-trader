#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  9 20:28:17 2018

@author: igor
"""

import params as p
import backtest as bt
import talib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from keras.models import Sequential, load_model
from keras import backend as K
from keras.layers import Dense, LSTM, Activation, Dropout
from sklearn.preprocessing import StandardScaler, MinMaxScaler, QuantileTransformer
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.optimizers import RMSprop
import datalib as dl
from joblib import dump, load
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

td = None
ds = None


def get_signal_str(s='', td=None):
    if s == '': s = get_signal(td)
    txt = p.pair + ':'
    txt += ' NEW' if s['new_trade'] else ' Same' 
    txt += ' Signal: ' + s['action'] 
    if p.short and s['action'] == 'Sell': txt += ' SHORT'
    txt += ' Open: '+str(s['open'])
    if s['action'] != 'Cash': txt += ' P/L: '+str(s['pnl'])+'%'
    if s['tp']: txt += ' TAKE PROFIT!'
    if s['sl']: txt += ' STOP LOSS!'
    
    return txt 


def get_signal(td, offset=-1):
    s = td.iloc[offset]
    pnl = round(100*(s.ctrf - 1), 2)
    sl = p.truncate(s.sl_price, p.price_precision)
    tp = p.truncate(s.tp_price, p.price_precision)
    
    return {'new_trade':s.new_trade, 'action':s.signal, 
            'open':s.open, 'open_ts':s.date, 
            'close':s.close, 'close_ts':s.date_to, 'pnl':pnl, 
            'sl':s.sl, 'sl_price':sl, 'tp':s.tp, 'tp_price':tp}


def add_features(ds):
    ds['VOL'] = ds['volume']/ds['volume'].rolling(window = p.vol_period).mean()
    ds['HH'] = ds['high']/ds['high'].rolling(window = p.hh_period).max() 
    ds['LL'] = ds['low']/ds['low'].rolling(window = p.ll_period).min()
    ds['DR'] = ds['close']/ds['close'].shift(1)
    ds['MA'] = ds['close']/ds['close'].rolling(window = p.sma_period).mean()
    ds['MA2'] = ds['close']/ds['close'].rolling(window = 2*p.sma_period).mean()
    ds['STD']= ds['close'].rolling(p.std_period).std()/ds['close']
    ds['RSI'] = talib.RSI(ds['close'].values, timeperiod = p.rsi_period)
    ds['WR'] = talib.WILLR(ds['high'].values, ds['low'].values, ds['close'].values, p.wil_period)
    ds['DMA'] = ds.MA/ds.MA.shift(1)
    ds['MAR'] = ds.MA/ds.MA2
    ds['ADX'] = talib.ADX(ds['high'].values, ds['low'].values, ds['close'].values, timeperiod = p.adx_period)
    ds['ATR'] = talib.ATR(ds['high'].values, ds['low'].values, ds['close'].values, timeperiod=14)
    ds['Price_Rise'] = np.where(ds['DR'] > 1, 1, 0)

    ds = ds.dropna()
    
    return ds


def get_train_test(X, y):
    # Separate train from test
    train_split = int(len(X)*p.train_pct)
    test_split = p.test_bars if p.test_bars > 0 else int(len(X)*p.test_pct)
    X_train, X_test, y_train, y_test = X[:train_split], X[-test_split:], y[:train_split], y[-test_split:]
    
    # Feature Scaling
    # Load scaler from file for test run
#    from sklearn.preprocessing import QuantileTransformer, MinMaxScaler
    scaler = p.cfgdir+'/sc.dmp'
    if p.train:
#        sc = QuantileTransformer(10)
#        sc = MinMaxScaler()
        sc = StandardScaler()
        X_train = sc.fit_transform(X_train)
        X_test = sc.transform(X_test)
        dump(sc, scaler)
    else:
        sc = load(scaler)
        # Uncomment if you need to upgrade scaler
        # dump(sc, scaler)
        X_train = sc.transform(X_train)
        X_test = sc.transform(X_test)
        
    return X_train, X_test, y_train, y_test


def plot_fit_history(h):
    # Plot model history
    # Accuracy: % of correct predictions 
#    plt.plot(h.history['acc'], label='Train Accuracy')
#    plt.plot(h.history['val_acc'], label='Test Accuracy')
    plt.plot(h.history['loss'], label='Train')
    plt.plot(h.history['val_loss'], label='Test')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.yscale('log')
    plt.legend()
    plt.grid(True)
    plt.show()


def train_model(X_train, X_test, y_train, y_test, file):
    print('*** Training model with '+str(p.units)+' units per layer ***')
    nn = Sequential()
    nn.add(Dense(units = p.units, kernel_initializer = 'uniform', activation = 'relu', input_dim = X_train.shape[1]))
    nn.add(Dense(units = p.units, kernel_initializer = 'uniform', activation = 'relu'))
    nn.add(Dense(units = 1, kernel_initializer = 'uniform', activation = 'sigmoid'))

    cp = ModelCheckpoint(file, monitor='val_loss', verbose=0, save_best_only=True, mode='min')
    nn.compile(optimizer = 'adam', loss = p.loss, metrics = ['accuracy'])
    history = nn.fit(X_train, y_train, batch_size = 100, 
                             epochs = p.epochs, callbacks=[cp], 
                             validation_data=(X_test, y_test), 
                             verbose=0)

    # Plot model history
    plot_fit_history(history)

    # Load Best Model
    nn = load_model(file) 
    
    return nn


# TODO: Use Long / Short / Cash signals
def gen_signal(ds, y_pred_val):
    td = ds.copy()
    td = td[-len(y_pred_val):]
    td['y_pred_val'] = y_pred_val
    td['y_pred'] = (td['y_pred_val'] >= p.signal_threshold)
    td = td.dropna()

    td['y_pred_id'] = np.trunc(td['y_pred_val'] * p.signal_scale)
    td['signal'] = td['y_pred'].map({True: 'Buy', False: 'Sell'})
    if p.ignore_signals is not None:
        td['signal'] = np.where(np.isin(td.y_pred_id, p.ignore_signals), np.NaN, td.signal)
        td['signal'] = td.signal.fillna(method='ffill')
    if p.hold_signals is not None:
        td['signal'] = np.where(np.isin(td.y_pred_id, p.hold_signals), 'Cash', td.signal)

    return td


# Inspired by:
# https://www.quantinsti.com/blog/artificial-neural-network-python-using-keras-predicting-stock-price-movement/
def runNN():
    global ds

    ds = dl.load_data(p.ticker, p.currency)
    ds = add_features(ds)
    
    # Separate input from output. Exclude last row
    X = ds[p.feature_list][:-1]
#    y = ds[['DR']].shift(-1)[:-1]
    y = ds[['Price_Rise']].shift(-1)[:-1]

    # Split Train and Test and scale
    X_train, X_test, y_train, y_test = get_train_test(X, y)    
    
    K.clear_session() # Required to speed up model load
    if p.train:
        file = p.cfgdir+'/model.nn'
        nn = train_model(X_train, X_test, y_train, y_test, file)
    else:
        file = p.model
        nn = load_model(file) 
#        print('Loaded best model: '+file)
     
    # Making prediction
    y_pred_val = nn.predict(X_test)

    # Generating Signals
    td = gen_signal(ds, y_pred_val)

    # Backtesting
    td = bt.run_backtest(td, file)
    print(str(get_signal_str(td=td)))

    return td


def train_test_nn(ds):
    # Separate input from output. Exclude last row
    X = ds[p.feature_list][:-1]
    y = ds[['DR']].shift(-1)[:-1]

    # Split Train and Test and scale
    train_split = int(len(X) * p.train_pct)
    test_split = p.test_bars if p.test_bars > 0 else int(len(X) * p.test_pct)
    X_train, X_test, y_train, y_test = X[:train_split], X[-test_split:], y[:train_split], y[-test_split:]

    # Feature Scaling
    scaler = p.cfgdir + '/sc.dmp'
    scaler1 = p.cfgdir + '/sc1.dmp'
    if p.train:
        sc = StandardScaler()
        X_train = sc.fit_transform(X_train)
        X_test = sc.transform(X_test)
        dump(sc, scaler)

        sc1 = MinMaxScaler()
        y_train = sc1.fit_transform(y_train)
        y_test = sc1.transform(y_test)
        dump(sc1, scaler1)

    else:
        sc = load(scaler)
        X_train = sc.transform(X_train)
        X_test = sc.transform(X_test)

        sc1 = load(scaler1)
        y_train = sc1.transform(y_train)
        y_test = sc1.transform(y_test)

    K.clear_session()  # Required to speed up model load
    if p.train:
        file = p.cfgdir + '/model.nn'
        print('*** Training model with ' + str(p.units) + ' units per layer ***')
        nn = Sequential()
        nn.add(Dense(units=p.units, kernel_initializer='uniform', activation='relu', input_dim=X_train.shape[1]))
        nn.add(Dense(units=p.units, kernel_initializer='uniform', activation='relu'))
        nn.add(Dense(units=1, kernel_initializer='uniform', activation='linear'))

        cp = ModelCheckpoint(file, monitor='val_loss', verbose=1, save_best_only=True, mode='min')
        nn.compile(optimizer='adam', loss=p.loss, metrics=['accuracy'])
        history = nn.fit(X_train, y_train, batch_size=len(X_train) if p.batch_size == 0 else p.batch_size,
                         epochs=p.epochs, callbacks=[cp],
                         validation_data=(X_test, y_test),
                         verbose=0)

        # Plot model history
        plot_fit_history(history)

        # Load Best Model
        nn = load_model(file)
    else:
        file = p.model
        nn = load_model(file)

        # Making prediction
    y_pred_val = nn.predict(X_test)
    y_pred_val = sc1.inverse_transform(y_pred_val)

    # Generating Signals
    td = gen_signal(ds, y_pred_val)

    # Backtesting
    td = bt.run_backtest(td, file)
    ds.to_csv(p.cfgdir + '/ds.csv')

    return td


def runNN1():
    global ds

    ds = dl.load_data(p.ticker, p.currency)

    ds['VOL'] = ds['volume']/ds['volume'].rolling(window = p.vol_period).mean()
    ds['HH'] = ds['high']/ds['high'].rolling(window = p.hh_period).max()
    ds['LL'] = ds['low']/ds['low'].rolling(window = p.ll_period).min()
    ds['DR'] = ds['close']/ds['close'].shift(1)
    ds['MA'] = ds['close']/ds['close'].rolling(window = p.sma_period).mean()
    ds['MA2'] = ds['close']/ds['close'].rolling(window = 2*p.sma_period).mean()
    ds['STD']= ds['close'].rolling(p.std_period).std()/ds['close']
    ds['RSI'] = talib.RSI(ds['close'].values, timeperiod = p.rsi_period)
    ds['WR'] = talib.WILLR(ds['high'].values, ds['low'].values, ds['close'].values, p.wil_period)
    ds['DMA'] = ds.MA/ds.MA.shift(1)
    ds['MAR'] = ds.MA/ds.MA2

    if p.btc_data:
        # p.reload must be True for this to work!
        ds1 = dl.load_data('ETH', 'BTC')
        ds = ds.join(ds1, on='time', rsuffix='_btc')
        ds['RSI_BTC'] = talib.RSI(ds['close_btc'].values, timeperiod=p.rsi_period)
        ds['BTC/ETH'] = ds['close'] / ds['close_btc']
        p.feature_list += ['RSI_BTC', 'BTC/ETH']

    ds = ds.dropna()
    td = train_test_nn(ds)
    return td


def runNN2():
    global ds

    ds = dl.load_data(p.ticker, p.currency)
    ds['DR'] = ds['close'] / ds['close'].shift(1)
    ds['ADR'] = ds['DR'].rolling(window=14).mean()

    calendar = dl.get_calendar(ds.date.min(), ds.date.max())
    ds = pd.merge(calendar, ds, on='date', how='left')
    ds = ds.dropna()

    for col in calendar.columns:
        if col == 'date':
            continue
        ds = dl.encode(ds, col, 359)

    td = train_test_nn(ds)
    return td


def runModel(conf):
    global td

    p.load_config(conf)
    td = globals()[p.model_type]()
    print(str(get_signal_str(td=td)))

    return td


def agg_signal(signals):
    res = 0
    for s in signals:
        if s == 'Buy':
            res += 1
    return res / len(signals)


def run_ensemble():
    global ds
    conf = p.conf
    # All In (from 0.5)
    # Strategy Return: 128611.19
    # Sortino Ratio: 8.35

    # Position Sizing (from 0)
    # Strategy Return: 71163.77
    # Sortino Ratio: 8.73

    d1 = runModel('ETHUSDNN1')
    d2 = runModel('ETHUSDNN1S')
    d3 = runModel('ETHUSDNN2')

    # Reloading config after previous models
    p.load_config(conf)

    d1 = d1[['date', 'open', 'high', 'low', 'close', 'signal']].rename(columns={'signal': 'signal_1'})
    d2 = d2[['date', 'signal']].rename(columns={'signal': 'signal_2'})
    d3 = d3[['date', 'signal']].rename(columns={'signal': 'signal_3'})
    ds = pd.merge(d1, d2, on='date', how='left')
    ds = pd.merge(ds, d3, on='date', how='left')
    y_pred_val = (np.where(ds.signal_1 == 'Buy', 1, 0)
                  + np.where(ds.signal_2 == 'Buy', 1, 0)
                  + np.where(ds.signal_3 == 'Buy', 1, 0)) / 3

    ds = gen_signal(ds, y_pred_val)
    ds['size'] = ds['y_pred_val']
    td = bt.run_backtest(ds, conf)

    return td


# runModel('ETHUSDNN')
# runModel('ETHUSDNN1')
# runModel('ETHUSDNN1S')
# runModel('ETHUSDNN2')
# runModel('ETHUSDENS')
