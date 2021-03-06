from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField

# ==================================
#       Abstract classes
# ==================================


class BlockTimeStamped(models.Model):
    """Model created in a specific Ethereum block"""
    creation_date_time = models.DateTimeField()
    creation_block = models.PositiveIntegerField()

    class Meta:
        abstract = True


class Contract(models.Model):
    """Represents the Ethereum smart contract instance"""
    address = models.CharField(max_length=40, primary_key=True)

    class Meta:
        abstract = True


class ContractCreatedByFactory(Contract, BlockTimeStamped):
    """Represents the Ethereum smart contract instance created by a factory (proxy contract)"""
    factory = models.CharField(max_length=40, db_index=True)  # factory contract creating the contract
    creator = models.CharField(max_length=40, db_index=True)  # address that initializes the transaction

    class Meta:
        abstract = True


# ==================================
#       Concrete classes
# ==================================


class Oracle(ContractCreatedByFactory):
    """Parent class of the Oracle contract"""
    is_outcome_set = models.BooleanField(default=False)
    outcome = models.DecimalField(max_digits=80, decimal_places=0, blank=True, null=True)


# Events
class Event(ContractCreatedByFactory):
    """Parent class of the event's classes."""
    oracle = models.ForeignKey(Oracle, related_name='event_oracle') # Reference to the Oracle contract
    collateral_token = models.CharField(max_length=40, db_index=True) # The ERC20 token address used in the event to exchange outcome token shares
    is_winning_outcome_set = models.BooleanField(default=False)
    outcome = models.DecimalField(max_digits=80, decimal_places=0, null=True)
    redeemed_winnings = models.DecimalField(max_digits=80, decimal_places=0, default=0) # Amount (in collateral token) of redeemed winnings once the event gets resolved


class ScalarEvent(Event):
    """Events with continuous domain of possible outcomes between two boundaries: lower and upper bound"""
    lower_bound = models.DecimalField(max_digits=80, decimal_places=0)
    upper_bound = models.DecimalField(max_digits=80, decimal_places=0)


class CategoricalEvent(Event):
    """Events with discrete domain of possible outcomes"""
    pass


# Tokens
class OutcomeToken(Contract):
    """Representation of the ERC20 token related with its respective outcome in the event.
    This token is created by the Event smart contract letting the event to control supply."""
    event = models.ForeignKey(Event, related_name='outcome_tokens') # The outcome token related event
    # index:
    # outcome position in the event's outcomes array (Categorical Event)
    # 0 for short and 1 for long position(Scalar Event)
    index = models.PositiveIntegerField()
    # total_supply: total amount of outcome tokens generated by the event for that outcome
    total_supply = models.DecimalField(max_digits=80, decimal_places=0, default=0)


class OutcomeTokenBalance(models.Model):
    """Outcome token balance owned by an ethereum address owner"""
    owner = models.CharField(max_length=40)
    outcome_token = models.ForeignKey(OutcomeToken)
    balance = models.DecimalField(max_digits=80, decimal_places=0, default=0)


# Event Descriptions
class EventDescription(models.Model):
    """Meta information of the event taken from IPFS"""
    title = models.TextField()
    description = models.TextField()
    resolution_date = models.DateTimeField()
    ipfs_hash = models.CharField(max_length=46, unique=True)


class ScalarEventDescription(EventDescription):
    """Description for the Scalar Event"""
    unit = models.TextField() # Example. USD, EUR, ETH
    decimals = models.PositiveIntegerField() # the unit precision


class CategoricalEventDescription(EventDescription):
    """Description for the Categorical Event"""
    outcomes = ArrayField(models.TextField()) # List of outcomes


# Oracles
class CentralizedOracle(Oracle):
    """Centralized oracle model"""
    owner = models.CharField(max_length=40, db_index=True) # owner can be updated
    old_owner = models.CharField(max_length=40, default=None, null=True) # useful for rollback
    event_description = models.ForeignKey(EventDescription, unique=False, null=True)


# Market
class Market(ContractCreatedByFactory):
    """Market created by a the Gnosis standard market factory"""
    stages = (
        (0, 'MarketCreated'),
        (1, 'MarketFunded'),
        (2, 'MarketClosed'),
    )

    event = models.ForeignKey(Event, related_name='markets')
    market_maker = models.CharField(max_length=40, db_index=True) # the address of the market maker
    fee = models.PositiveIntegerField()
    funding = models.DecimalField(max_digits=80, decimal_places=0, null=True)
    net_outcome_tokens_sold = ArrayField(models.DecimalField(max_digits=80, decimal_places=0), null=False) # acumulative distribution of sold outcome tokens
    withdrawn_fees = models.DecimalField(max_digits=80, decimal_places=0, default=0)
    stage = models.PositiveIntegerField(choices=stages, default=0)
    revenue = models.DecimalField(max_digits=80, decimal_places=0)
    collected_fees = models.DecimalField(max_digits=80, decimal_places=0)
    marginal_prices = ArrayField(models.DecimalField(max_digits=5, decimal_places=4))
    trading_volume = models.DecimalField(max_digits=80, decimal_places=0)


class Order(BlockTimeStamped):
    """Parent class defining a market related order"""
    market = models.ForeignKey(Market, related_name='orders')
    sender = models.CharField(max_length=40, db_index=True)
    outcome_token = models.ForeignKey(OutcomeToken, to_field='address', null=True)
    outcome_token_count = models.DecimalField(max_digits=80, decimal_places=0) # the amount of outcome tokens bought or sold
    net_outcome_tokens_sold = ArrayField(models.DecimalField(max_digits=80, decimal_places=0)) # represents the outcome tokens distrubition at the buy/sell order moment
    marginal_prices = ArrayField(models.DecimalField(max_digits=5, decimal_places=4)) # represent the marginal price of each outcome at the time of the market order


class BuyOrder(Order):
    cost = models.DecimalField(max_digits=80, decimal_places=0)
    outcome_token_cost = models.DecimalField(max_digits=80, decimal_places=0)
    fees = models.DecimalField(max_digits=80, decimal_places=0)


class SellOrder(Order):
    profit = models.DecimalField(max_digits=80, decimal_places=0)
    outcome_token_profit = models.DecimalField(max_digits=80, decimal_places=0)
    fees = models.DecimalField(max_digits=80, decimal_places=0)


class ShortSellOrder(Order):
    cost = models.DecimalField(max_digits=80, decimal_places=0)
