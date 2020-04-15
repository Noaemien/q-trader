#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Kraken API
# https://github.com/dominiktraxl/pykrakenapi

# CCXT API
# https://github.com/ccxt/ccxt/wiki/Manual#overriding-unified-api-params

"""
Created on Mon Dec 25 18:06:07 2017

@author: imonahov
"""
import ccxt
import time
import params as p
import mysecrets as s

# TODO: move this to init() method
ex = ccxt.kraken({
#    'verbose': True,    
    'apiKey': s.exchange_api_key,
    'secret': s.exchange_sk,
    'timeout': 20000,
#    'session': cfscrape.create_scraper(), # To avoid Cloudflare block => still fails with 520 Origin Error
    'enableRateLimit': True,
    'rateLimit': 1000 # Rate Limit set to 1 sec to avoid issues
})

markets = ex.load_markets()

'''
hitbtc = ccxt.hitbtc({'verbose': True})
bitmex = ccxt.bitmex()
huobi  = ccxt.huobi()
exmo   = ccxt.exmo({
    'apiKey': 'YOUR_PUBLIC_API_KEY',
    'secret': 'YOUR_SECRET_PRIVATE_KEY',
})

hitbtc_markets = hitbtc.load_markets()

print(hitbtc.id, hitbtc_markets)
print(bitmex.id, bitmex.load_markets())
print(huobi.id, huobi.load_markets())

print(hitbtc.fetch_order_book(hitbtc.symbols[0]))
print(bitmex.fetch_ticker('BTC/USD'))
print(huobi.fetch_trades('LTC/CNY'))

print(exmo.fetch_balance())

# sell one ฿ for market price and receive $ right now
print(exmo.id, exmo.create_market_sell_order('BTC/USD', 1))

# limit buy BTC/EUR, you pay €2500 and receive ฿1  when the order is closed
print(exmo.id, exmo.create_limit_buy_order('BTC/EUR', 1, 2500.00))

# pass/redefine custom exchange-specific order params: type, amount, price, flags, etc...
exmo.create_market_buy_order('BTC/USD', 1, {'trading_agreement': 'agree'})
'''

'''
Executes Market Order on exchange
Example: Buy BTC with 100 EUR
order = market_order('buy', 'BTC', 'EUR', 100)
Example: Sell 0.0001 BTC
order = market_order('sell', 'BTC', 'EUR', 0.0001)
'''

# Returns day open price
def get_price(item='open'):
    ticker = ex.fetch_ticker(p.pair)
    return ticker[item]

def get_ticker():
    ticker = ex.fetch_ticker(p.pair)
    return ticker

def get_balance(asset=''):
    if asset == '': asset = p.currency
    balance = ex.fetch_balance()['total']
    return balance[asset]

def get_balance_str():
    balance = ex.fetch_balance()['total']
    return p.currency+': '+str(balance[p.currency])+', '+p.ticker+': '+str(balance[p.ticker])

def get_total_value():
    bal = ex.fetch_balance()['total']
    amt = 0
    for c in bal:
        if c == 'USD' or bal[c] == 0: price = 1
        else: price = ex.fetch_ticker(c+'/USD')['last']
        
        amt = amt + bal[c] * price
    
    return p.truncate(amt, 2)    
    
def create_order(side, amount=0, price=0, ordertype='', leverage=1, wait=True):
    params = {}
    if ordertype == '': ordertype = p.order_type
    if leverage > 1: params['leverage'] = leverage
    # TODO: Use 0% if price is better than order price to avoid market order
    if price == 0 and ordertype == 'limit': params['price'] = '#0%'

    order = ex.create_order(p.pair, ordertype, side, amount, price, params)    
    order = ex.fetchOrder(order['id'])
    print('***** Order Created *****')
    print(order)

    # Wait till order is executed
    if wait: order = wait_order(order['id'])

    return order

def fetchOrder(order_id):
    order = {}
    try:
        order = ex.fetchOrder(order_id)
    except Exception as e:
        print(e)
    
    return order

def wait_order(order_id):
    print('Waiting for order '+order_id+' to be executed ...')
    while True:
        order = fetchOrder(order_id)
        if order != {} and order['status'] in ['closed','canceled','expired']:
            print('***** Order '+order['status']+' *****')
            print(order)
            return order
        time.sleep(p.order_wait)

#def get_order_price(order_type):
#    orders = ex.fetchClosedOrders(p.pair)
#    return orders[0]['info']['price']

def get_order_size(action, price=0):
    # Calculate position size based on portfolio value %
    if price == 0: price = get_price()
    amount = get_balance() * p.order_pct
    size = p.truncate(amount/price, p.order_precision)

    # Applying order size limit
    if p.order_size > 0: size = min(size, p.order_size)
    if action == 'Sell' and p.max_short > 0: size = min(size, p.max_short)
    return size

def close_position(action, price=0, ordertype='', wait=True):
    res = {}
    if ordertype == '': ordertype = p.order_type
    
    if action == 'Sell':
        res = create_order('buy', 0, price, ordertype, p.leverage, wait)
    elif action == 'Buy':
        amount = get_balance(p.ticker)
        res = create_order('sell', amount, price, ordertype, 1, wait)

    return res

def open_position(action, price=0, ordertype='', wait=True):
    res = {}
    amount = get_order_size(action, price)
    if amount == 0: raise Exception('Not enough funds to open position')
    lot = amount
    side = action.lower()
    
    if action == 'Sell':
        leverage = p.leverage
    elif action == 'Buy':
        leverage = 1
    else: 
        raise Exception('Invalid action provided: '+action)

    while lot >= p.min_equity:
        try:
            res = create_order(side, lot, price, ordertype, leverage, wait)
            print('Created order of size '+str(lot))
            if lot == amount: break # Position opened as expected
        except ccxt.InsufficientFunds:
            lot = p.truncate(lot/2, p.order_precision)
            print('Insufficient Funds. Reducing order size to '+str(lot))
            
    return res
        
def take_profit(action, price):
    ticker = get_ticker()
    if action == 'Buy' and price >= ticker['ask'] or action == 'Sell' and price <= ticker['bid']:        
        close_position(action, ordertype='take-profit', price=price, wait=False)
        return 'TP set at %s' % price
    return 'TP is not set'

def stop_loss(action, price):
    ticker = get_ticker()
    if action == 'Buy' and price <= ticker['bid'] or action == 'Sell' and price >= ticker['ask']:        
        close_position(action, ordertype='stop-loss', price=price, wait=False)
        return 'SL set at %s' % price
    return 'SL is not set'

def has_orders(types=[]):
    if types == []: types = [p.order_type]
    for order in ex.fetchOpenOrders(p.pair):
        if order['type'] in types: return True
    return False

def wait_orders(types=[]):
    if types == []: types = [p.order_type]
    for order in ex.fetchOpenOrders(p.pair):
        if order['type'] in types: wait_order(order['id'])

def has_sl_order():
    return has_orders(['stop-loss'])
    
def has_tp_order():
    return has_orders(['take-profit'])

def get_position():
    if get_balance(p.ticker) > p.min_equity: return 'Buy'
    if not p.short: return 'Sell'

    # Check short position
    res = ex.privatePostOpenPositions()
    if len(res['result']) > 0: return 'Sell'
    
    return 'Cash'

def cancel_orders(types=[]):
    for order in ex.fetchOpenOrders(p.pair):
        if types == [] or order['type'] in types:
            print("Cancelling Order:")
            print(order)
            ex.cancelOrder(order['id'])    

def cancel_sl():
    cancel_orders(['stop-loss'])

def cancel_tp():
    cancel_orders(['take-profit'])

def test_order1():
    p.load_config('ETHUSDNN')
    p.order_size = 0.02
    # Print available API methods
    print(dir(ex))
    
    # Buy
    ex.fetch_balance()['total']
    # Close SL Order
    cancel_orders()
    
    ex.fetchOpenOrders()
    
    ex.fetchClosedOrders('ETH/USD')

    # Get Open Positions
    ex.privatePostOpenPositions()

    # Limit Order with current price
    create_order('Buy', 'limit', 0.02, {'price':'+0%'})
    
    ex.createOrder('ETH/USD', 'market', 'buy', 0.02)

def test_order2():
    p.load_config('ETHUSDNN')

    # Create Market Order
    ex.createOrder('ETH/USD', 'market', 'buy', 0.02)
    ex.createOrder('ETH/USD', 'market', 'sell', 0.02)
    ex.createOrder('ETH/USD', 'market', 'buy', 0.02, 0) # Price is ignored

    # Create Limit Order for fixed price
    ex.createOrder('ETH/USD', 'limit', 'buy', 0.02, 100)
    # Create Limit Order for -1% to market price
    ex.createOrder('ETH/USD', 'limit', 'buy', 0.02, 0, {'price':'-1%'})

    # Fetch Open Orders
    orders = ex.fetchOpenOrders()
    # Order Size
    orders[0]['amount']

    ex.fetchBalance()['ETH']

def test_order3():
    p.load_config('ETHUSDNN')
    p.order_size = 0.02
    p.order_wait = 10
    open_position('Buy')
    print(get_balance())
    
    res = take_profit('Buy', 200)
    res = stop_loss('Buy', 100)
    res = close_position('Buy', wait=False)
    get_balance('ETH')
    ex.fetchOpenOrders()
    cancel_sl()
    cancel_tp()
    cancel_orders()
    get_price()

    res = ex.privatePostOpenPositions()
    len(res['result'])
    open_position('Sell')
    close_position('Sell', wait=False)
    ex.fetchOpenOrders()
    get_price()
    create_order('buy', 10, 215.19, 'stop-loss', 1, False)
