import time
from functools import wraps

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import MessageHandler, Filters, run_async, ConversationHandler, CommandHandler, RegexHandler

from backend.models import Message, Invite, TGUser, Event
from backend.tgbot.base import TelegramBotApi
from backend.tgbot.texts import *
from backend.tgbot.utils import logger
# from backend.get_google_files import Google_spread_sheet

CHOOSING = 0
CHECK_EMAIL = 1
BROADCAST = 2
# SCHEDULE = 3

# schedule_table = Google_spread_sheet()


NOT_REGISTERED_KEYBOARD = [[BUTTON_CHECK_EMAIL, BUTTON_SHEDULE, BUTTON_REGISTRATION]]
SHEDULE_KEYBOARD = [[BUTTON_10_MAY_SHEDULE, BUTTON_11_MAY_SHEDULE]]
REGISTRED_KEYBOARD = [[]]
ADMIN_KEYBOARD = [[BUTTON_CHECK_EMAIL, BUTTON_SHEDULE, BUTTON_REGISTRATION, BUTTON_CREATE_BROADCAST]]


def kb(user: TGUser):
    return ReplyKeyboardMarkup(ADMIN_KEYBOARD if user.is_admin else NOT_REGISTERED_KEYBOARD, one_time_keyboard=True)


def save_msg(f):
    @wraps(f)
    def save(api: TelegramBotApi, update):
        Message.from_update(api, update)
        return f(api, update)

    return save


def with_user(f):
    @wraps(f)
    def get_user(api: TelegramBotApi, update):
        user = api.get_user(update.message.chat_id)
        return f(api, user, update)

    return get_user


@run_async
@save_msg
@with_user
def menu(api: TelegramBotApi, user: TGUser, update):
    logger.info('User {} have started conversation.'.format(user))
    update.message.reply_text(
        TEXT_HELLO,
        reply_markup=kb(user))

    return CHOOSING


@run_async
@save_msg
@with_user
def check_email(api: TelegramBotApi, user: TGUser, update):
    text = update.message.text
    logger.info('User {} have chosen {} '.format(user, text))
    update.message.reply_text(TEXT_ENTER_EMAIL,
                              reply_markup=ReplyKeyboardRemove())
    return CHECK_EMAIL


@run_async
@save_msg
@with_user
def email_in_list(api: TelegramBotApi, user: TGUser, update):
    email = update.message.text
    logger.info('{}'.format(email))
    if Invite.objects.filter(email=email).first() is not None:
        update.message.reply_text(TEXT_EMAIL_OK,
                                  reply_markup=kb(user))
    else:
        update.message.reply_text(TEXT_EMAIL_NOT_OK,
                                  reply_markup=kb(user))

    if user.last_checked_email != email:
        user.is_notified = False  # todo ????
        user.last_checked_email = email
        user.save()
    return CHOOSING


@run_async
@save_msg
@with_user
def show_schedule(api: TelegramBotApi, user: TGUser, update):
    schedule = '\n'.join(str(e) for e in Event.objects.all())
    # custom_keyboard = ReplyKeyboardMarkup(SHEDULE_KEYBOARD, one_time_keyboard=True)
    update.message.reply_text(TEXT_SHOW_SCHEDULE
                              , reply_markup=kb(user))
    return CHOOSING

# @run_async
# @save_msg
# @with_user
# def schedule_day(api: TelegramBotApi, user: TGUser, update):
#     day_table = schedule_table.get_data()
#     update.message.reply_text('{}'.format(day_table.to_string(index=False))
#                               , reply_markup=kb(user))
#     return CHOOSING


@run_async
@save_msg
@with_user
def can_spam(api: TelegramBotApi, user: TGUser, update):
    user.is_subscribed = True
    user.save()
    logger.info('{} subscribed for notification'.format(user))
    update.message.reply_text(TEXT_AFTER_SUB,
                              reply_markup=kb(user))
    return CHOOSING


@run_async
@save_msg
@with_user
def skip_email(api: TelegramBotApi, user: TGUser, update):
    logger.info("User %s did not send an email.", user)
    update.message.reply_text(TEXT_SKIP_EMAIL, reply_markup=kb(user))
    return CHOOSING


@run_async
@save_msg
@with_user
def create_broadcast(api: TelegramBotApi, user: TGUser, update):
    logger.info("User %s initiated broadcast.", user)
    if not user.is_admin:
        update.message.reply_text(TEXT_NOT_ADMIN, reply_markup=kb(user))
    update.message.reply_text(TEXT_ENTER_BROADCAST)
    return BROADCAST


@run_async
@save_msg
@with_user
def send_broadcast(api: TelegramBotApi, user: TGUser, update):
    broadcast_text = update.message.text
    for u in TGUser.objects.all():
        try:
            api.bot.send_message(u.tg_id, broadcast_text)
            time.sleep(.1)
        except:
            logger.exception('Error sending broadcast to user {}'.format(u))
    update.message.reply_text(TEXT_BROADCAST_DONE, reply_markup=kb(user))


@run_async
@save_msg
@with_user
def cancel(api: TelegramBotApi, user: TGUser, update):
    logger.info("User %s canceled the conversation.", user)
    update.message.reply_text(TEXT_BYE,
                              reply_markup=ReplyKeyboardRemove())


def rhandler(text, callback):
    return RegexHandler('^({})$'.format(text), callback)


handlers = [
    ConversationHandler(
        entry_points=[CommandHandler('start', menu)],

        states={
            CHOOSING: [
                rhandler(BUTTON_CHECK_EMAIL, check_email),
                rhandler(BUTTON_SHEDULE, show_schedule),
                rhandler(BUTTON_REGISTRATION, can_spam),
                rhandler(BUTTON_CREATE_BROADCAST, create_broadcast)
            ],

            # SCHEDULE:[
            #     rhandler(BUTTON_10_MAY_SHEDULE, schedule_day),
            #     rhandler(BUTTON_11_MAY_SHEDULE, schedule_day)
            # ],

            CHECK_EMAIL: [MessageHandler(Filters.text, email_in_list),
                          CommandHandler('skip', skip_email)],

            BROADCAST: [MessageHandler(Filters.text, send_broadcast),
                        CommandHandler('skip', skip_email)]  # fixme
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
]
