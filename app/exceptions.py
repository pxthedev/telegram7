class BotError(Exception):
    pass


class UserNotFound(BotError):
    pass


class ProductNotFound(BotError):
    pass


class InsufficientStock(BotError):
    pass


class InsufficientBalance(BotError):
    pass


class AlreadyPurchased(BotError):
    pass


class InvalidAmount(BotError):
    pass


class CustomerDataRequired(BotError):
    pass


class PaymentError(BotError):
    pass


class PaymentNotFound(BotError):
    pass


class PaymentExpired(BotError):
    pass


class InvalidWebhook(BotError):
    pass


class AdminRequired(BotError):
    pass
