"""
The portfolio rebalancing bot will buy and sell to maintain a
constant asset allocation ratio of exactly 50/50 = fiat/BTC
"""

import strategy
import goxapi

DISTANCE    = 5     # percent price distance of next rebalancing orders
MARKER      = 7     # lowest digit of price to identify bot's own orders
COIN        = 1E8   # number of satoshi per coin, this is a constant.

def add_marker(price, marker):
    """encode a marker in the price value to find bot's own orders"""
    return price / 10 * 10 + marker

def has_marker(price, marker):
    """return true if the price value has the marker"""
    return (price % 10) == marker

def mark_own(price):
    """return the price with our own marker embedded"""
    return add_marker(price, MARKER)

def is_own(price):
    """return true if this price has our own marker"""
    return has_marker(price, MARKER)



class Strategy(strategy.Strategy):
    """a protfolio rebalancing bot"""
    def __init__(self, gox):
        strategy.Strategy.__init__(self, gox)
        self.last_trade = 0
        self.temp_halt = False

    def slot_before_unload(self, _sender, _data):
        pass

    def slot_keypress(self, gox, (key)):
        """a key has been pressed"""

        if key == ord("c"):
            # remove existing rebalancing orders
            self.debug("canceling all rebalancing orders")
            self.temp_halt = True
            self.cancel_orders()

        if key == ord("p"):
            # create the initial two rebalancing orders. Before you
            # do this the portfolio should already be balanced.
            self.debug("adding new initial rebalancing orders")
            book = self.gox.orderbook
            self.temp_halt = False
            self.place_orders((book.bid + book.ask) / 2)

        if key == ord("u"):
            gox.client.channel_subscribe()

        if key == ord("i"):
            price = (gox.orderbook.bid + gox.orderbook.ask) / 2
            vol_buy = self.get_buy_at_price(price)
            line1 = "BTC difference: " + goxapi.int2str(vol_buy, "BTC")            
            if len(self.gox.wallet):
                line1 += "\t"
                for currency in self.gox.wallet:
                    line1 += currency + " " \
                    + goxapi.int2str(self.gox.wallet[currency], currency).strip() \
                    + " + "
                line1 = line1.strip(" +")
            self.debug(line1)

        if key == ord("b"):
            price = (gox.orderbook.bid + gox.orderbook.ask) / 2
            vol_buy = self.get_buy_at_price(price)
            if abs(vol_buy) > 0.01 * COIN:
                self.temp_halt = True
                self.cancel_orders()
                if vol_buy > 0:
                    self.debug("buy %f at market" %
                        goxapi.int2float(vol_buy, "BTC"))
                    gox.buy(0, vol_buy)
                else:
                    self.debug("sell %f at market" %
                        goxapi.int2float(-vol_buy, "BTC"))
                    gox.sell(0, -vol_buy)



    def cancel_orders(self):
        """cancel all rebalancing orders, we identify
        them through the marker in the price value"""
        must_cancel = []
        for order in self.gox.orderbook.owns:
            if is_own(order.price):
                must_cancel.append(order)

        for order in must_cancel:
            self.gox.cancel(order.oid)

    def get_buy_at_price(self, price_int):
        """calculate amount of BTC needed to buy at price to achieve
        rebalancing. price and return value are in mtgox integer format"""
        currency = self.gox.currency
        fiat_have = goxapi.int2float(self.gox.wallet[currency], currency)
        btc_have  = goxapi.int2float(self.gox.wallet["BTC"], "BTC")
        price_then = goxapi.int2float(price_int, currency)

        btc_value_then = btc_have * price_then
        diff = fiat_have - btc_value_then
        diff_btc = diff / price_then
        must_buy = diff_btc / 2
        return goxapi.float2int(must_buy, "BTC")

    def place_orders(self, center):
        """place two new rebalancing orders above and below center price"""
        currency = self.gox.currency
        step = int(center * DISTANCE / 100.0)
        next_sell = mark_own(center + step)
        next_buy  = mark_own(center - step)

        sell_amount = -self.get_buy_at_price(next_sell)
        buy_amount = self.get_buy_at_price(next_buy)

        if sell_amount < 0.01 * COIN:
            sell_amount = int(0.01 * COIN)
            self.debug("WARNING! minimal sell amount adjusted to 0.01")

        if buy_amount < 0.01 * COIN:
            buy_amount = int(0.01 * COIN)
            self.debug("WARNING! minimal buy amount adjusted to 0.01")

        self.debug("new buy order %f at %f" % (
            goxapi.int2float(buy_amount, "BTC"),
            goxapi.int2float(next_buy, currency)
        ))
        self.gox.buy(next_buy, buy_amount)

        self.debug("new sell order %f at %f" % (
            goxapi.int2float(sell_amount, "BTC"),
            goxapi.int2float(next_sell, currency)
        ))
        self.gox.sell(next_sell, sell_amount)


    def slot_trade(self, gox, (date, price, volume, typ, own)):
        """a trade message has been receivd"""
        # not interested in other people's trades
        if not own:
            return

        # not interested in manually entered (not bot) trades
        if not is_own(price):
            return

        # Trigger the info display so it gets logged, before the trade info
        self.slot_keypress(self, gox, ord("i"))
        
        # Continue with trade info
        text = {"bid": "sold", "ask": "bought"}[typ]
        self.debug("*** %s %f at %f" % (
            text,
            goxapi.int2float(volume, "BTC"),
            goxapi.int2float(price, gox.currency)
        ))
        self.last_trade = price
        self.check_trades()

    def slot_owns_changed(self, orderbook, _dummy):
        """status or amount of own open orders has changed"""
        self.check_trades()

    def check_trades(self):
        """find out if we need to place new orders and do it if neccesary"""

        # bot temporarily disabled
        if self.temp_halt:
            return

        # still waiting for submitted orders,
        # can wait for next signal
        if self.gox.count_submitted:
            return

        # we count the open and pending orders
        count = 0
        count_pending = 0
        book = self.gox.orderbook
        for order in book.owns:
            if is_own(order.price):
                if order.status == "open":
                    count += 1
                else:
                    count_pending += 1

        # as long as there are ANY pending orders around we
        # just do nothing and wait for the next signal
        if count_pending:
            return

        # if count is exacty 1 then one of the orders must have been filled,
        # now we cancel the other one and place two fresh orders in the
        # distance of DISTANCE around current price.
        if count == 1:
            price = self.last_trade
            self.last_trade = 0
            if not price:
                price = (book.ask + book.bid) / 2
                self.debug(
                    "*** missed trade message, using current price %f" %
                    goxapi.int2float(price, self.gox.currency)
                )
            self.cancel_orders()
            self.place_orders(price)