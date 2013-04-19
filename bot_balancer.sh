#!/bin/sh
# https://bitcointalk.org/index.php?topic=148462.msg1854636#msg1854636
# https://gist.github.com/prof7bit/5395900
# https://bitcointalk.org/index.php?topic=148462.msg1886914#msg1886914

# "p": place 2 orders above and below price. 
# "c": cancel orders and effectively stop the bot
# "u": update own order list, depth, history, wallet and everything
# "i": display how much it is out of balance at current price (negative: must sell, positive: must buy)
# "b":balance immediately (cancel orders and then buy/sell at market to rebalance)
./goxtool.py --protocol=socketio --use-http --strategy=_balancer.py