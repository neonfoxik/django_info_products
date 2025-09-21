from telebot.types import Message, CallbackQuery
from django.utils import timezone
from bot import bot, logger
from bot.models import User, PromoCode
from bot.keyboards import get_promocode_menu_markup, get_promocode_list_markup, get_promocode_detail_markup


# Состояния для работы с промокодами
promocode_state = {}


def promocode_menu(call: CallbackQuery) -> None:
    """Показывает меню управления промокодами"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        if not user.is_admin and not is_owner:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🎫 Управление промокодами\n\nВыберите действие:",
            reply_markup=get_promocode_menu_markup()
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в promocode_menu: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def promocode_add(call: CallbackQuery) -> None:
    """Запрашивает промокоды для добавления"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        if not is_owner:
            bot.answer_callback_query(call.id, "Только владелец бота может добавлять промокоды")
            return
        
        promocode_state[call.message.chat.id] = {"awaiting_promocodes": True}
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="➕ Добавление промокодов\n\n"
                 "Отправьте промокоды одним сообщением:\n"
                 "• Один промокод в строке\n"
                 "• Или несколько промокодов, каждый с новой строки\n\n"
                 "Пример:\n"
                 "ZZ321D\n"
                 "QEWCZ21\n"
                 "ZXZCSED32"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в promocode_add: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def handle_promocode_text(message: Message) -> bool:
    """Обрабатывает текст с промокодами"""
    try:
        if message.chat.id not in promocode_state:
            return False
        
        state = promocode_state[message.chat.id]
        if not state.get("awaiting_promocodes"):
            return False
        
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=message.chat.id,
            is_active=True
        ).exists()
        
        if not is_owner:
            bot.send_message(
                chat_id=message.chat.id,
                text="❌ Только владелец бота может добавлять промокоды"
            )
            if message.chat.id in promocode_state:
                del promocode_state[message.chat.id]
            return True
        
        # Разбираем промокоды из текста
        promocodes_text = message.text.strip()
        promocodes_lines = [line.strip().upper() for line in promocodes_text.split('\n') if line.strip()]
        
        if not promocodes_lines:
            bot.send_message(
                chat_id=message.chat.id,
                text="❌ Не найдено ни одного промокода. Попробуйте еще раз."
            )
            return True
        
        # Создаем промокоды
        created_count = 0
        skipped_count = 0
        
        for code in promocodes_lines:
            if len(code) > 50:
                skipped_count += 1
                continue
                
            try:
                promo, created = PromoCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'created_by': user,
                        'is_active': True,
                        'is_used': False
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Ошибка создания промокода {code}: {e}")
                skipped_count += 1
        
        # Удаляем состояние
        del promocode_state[message.chat.id]
        
        # Отправляем результат
        result_text = f"✅ Промокоды обработаны:\n"
        result_text += f"• Создано: {created_count}\n"
        if skipped_count > 0:
            result_text += f"• Пропущено (уже существуют или ошибка): {skipped_count}\n"
        
        bot.send_message(
            chat_id=message.chat.id,
            text=result_text,
            reply_markup=get_promocode_menu_markup()
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в handle_promocode_text: {e}")
        if message.chat.id in promocode_state:
            del promocode_state[message.chat.id]
        bot.send_message(
            chat_id=message.chat.id,
            text="Произошла ошибка при обработке промокодов."
        )
        return True


def promocode_list(call: CallbackQuery) -> None:
    """Показывает список промокодов"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        if not user.is_admin and not is_owner:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        # Получаем последние 10 промокодов
        promocodes = PromoCode.objects.all()[:10]
        
        if not promocodes:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📋 Список промокодов пуст.\n\nСоздайте первый промокод, нажав 'Добавить промокоды'.",
                reply_markup=get_promocode_menu_markup()
            )
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📋 Список промокодов\n\nВыберите промокод для просмотра деталей:",
                reply_markup=get_promocode_list_markup(promocodes)
            )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в promocode_list: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def promocode_detail(call: CallbackQuery) -> None:
    """Показывает детали промокода"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        if not user.is_admin and not is_owner:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        promo_id = int(call.data.split('_')[-1])
        promo = PromoCode.objects.get(id=promo_id)
        
        # Формируем текст с деталями
        detail_text = f"🎫 Промокод: {promo.code}\n\n"
        detail_text += f"📊 Статус: "
        if promo.is_used:
            detail_text += "Использован ❌"
        elif promo.is_active:
            detail_text += "Активен ✅"
        else:
            detail_text += "Неактивен ⏸️"
        
        detail_text += f"\n📅 Создан: {promo.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if promo.created_by:
            detail_text += f"👤 Создан администратором: {promo.created_by.user_name}\n"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=detail_text,
            reply_markup=get_promocode_detail_markup(promo_id)
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в promocode_detail: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def promocode_toggle(call: CallbackQuery) -> None:
    """Переключает статус промокода"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        if not user.is_admin and not is_owner:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        promo_id = int(call.data.split('_')[-1])
        promo = PromoCode.objects.get(id=promo_id)
        
        promo.is_active = not promo.is_active
        promo.save()
        
        status_text = "активирован" if promo.is_active else "деактивирован"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Промокод {promo.code} {status_text}.",
            reply_markup=get_promocode_detail_markup(promo_id)
        )
        bot.answer_callback_query(call.id, f"Промокод {status_text}")
        
    except Exception as e:
        logger.error(f"Ошибка в promocode_toggle: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def promocode_delete(call: CallbackQuery) -> None:
    """Удаляет промокод"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        if not user.is_admin and not is_owner:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        promo_id = int(call.data.split('_')[-1])
        promo = PromoCode.objects.get(id=promo_id)
        promo_code = promo.code
        
        promo.delete()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🗑️ Промокод {promo_code} удален.",
            reply_markup=get_promocode_menu_markup()
        )
        bot.answer_callback_query(call.id, "Промокод удален")
        
    except Exception as e:
        logger.error(f"Ошибка в promocode_delete: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def get_user_promocode(call: CallbackQuery) -> None:
    """Пользователь получает промокод"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        
        # Проверяем, не получал ли пользователь уже промокод
        if user.received_promocode:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🎫 Вы уже получили промокод!\n\n"
                     f"Ваш промокод: **{user.received_promocode}**\n\n"
                     f"Один пользователь может получить только один промокод.",
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "Промокод уже получен")
            return
        
        # Ищем доступный промокод
        available_promo = PromoCode.objects.filter(
            is_active=True,
            is_used=False
        ).first()
        
        if not available_promo:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="😔 К сожалению, сейчас нет доступных промокодов.\n\n"
                     "Попробуйте позже или обратитесь в поддержку.",
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "Нет доступных промокодов")
            return
        
        # Выдаем промокод пользователю
        promo_code = available_promo.code
        user.received_promocode = promo_code
        user.save()
        
        # Удаляем промокод из базы данных
        available_promo.delete()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🎉 Поздравляем! Вы получили промокод!\n\n"
                 f"**Ваш промокод: {promo_code}**\n\n"
                 f"💡 Используйте его при оформлении заказа для получения скидки или специального предложения!",
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "Промокод получен!")
        
    except Exception as e:
        logger.error(f"Ошибка в get_user_promocode: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")
