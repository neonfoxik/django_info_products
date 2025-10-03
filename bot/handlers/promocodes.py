from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.conf import settings
from django.utils import timezone
from bot import bot, logger
from bot.models import User, PromoCode, PromoCodeCategory
from bot.keyboards import (
    get_promocode_menu_markup,
    get_promocode_list_markup,
    get_promocode_detail_markup,
    get_categories_markup,
    get_promocode_categories_admin_markup,
    get_promocode_category_actions_markup,
    back_to_main_markup,
)


# Состояния для работы с промокодами
promocode_state = {}


def promocode_menu(call: CallbackQuery) -> None:
    """Показывает меню управления промокодами"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner_db = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(call.message.chat.id)
        is_owner = is_owner_db or is_owner_env
        
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
    """Просит выбрать категорию, затем запрашивает промокоды для добавления"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        
        # Разрешаем только главному админу или OWNER_ID
        if not is_owner and not user.is_super_admin:
            bot.answer_callback_query(call.id, "Только владелец бота может добавлять промокоды")
            return
        categories = PromoCodeCategory.objects.filter(is_active=True).order_by('name')
        if not categories.exists():
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Нет активных категорий промокодов. Создайте их в админке Django.",
                reply_markup=get_promocode_menu_markup()
            )
            bot.answer_callback_query(call.id)
            return
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Выберите категорию для добавления промокодов:",
            reply_markup=get_promocode_categories_admin_markup(categories, back_callback="promocode_menu")
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
        is_owner_db = OwnerSettings.objects.filter(
            owner_telegram_id=message.chat.id,
            is_active=True
        ).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(message.chat.id)
        is_owner = is_owner_db or is_owner_env
        
        if not is_owner and not user.is_super_admin:
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
                        'is_used': False,
                        'category': state.get('category')
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Ошибка создания промокода {code}: {e}")
                skipped_count += 1
        
        # Отправляем результат
        result_text = f"✅ Промокоды обработаны:\n"
        result_text += f"• Создано: {created_count}\n"
        if skipped_count > 0:
            result_text += f"• Пропущено (уже существуют или ошибка): {skipped_count}\n"
        
        result_text += "\n💡 Инструкции можно добавить в админ-панели Django."
        
        bot.send_message(
            chat_id=message.chat.id,
            text=result_text,
            reply_markup=get_promocode_menu_markup()
        )
        
        # Удаляем состояние
        del promocode_state[message.chat.id]
        
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


def handle_promocode_document(message: Message) -> bool:
    """Обрабатывает загруженный текстовый файл с промокодами (по одному в строке)"""
    try:
        if message.chat.id not in promocode_state:
            return False
        state = promocode_state[message.chat.id]
        if not state.get("awaiting_promocodes"):
            return False

        from bot.models import OwnerSettings
        user = User.objects.get(telegram_id=message.chat.id)
        is_owner_db = OwnerSettings.objects.filter(
            owner_telegram_id=message.chat.id,
            is_active=True
        ).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(message.chat.id)
        is_owner = is_owner_db or is_owner_env
        if not is_owner and not user.is_super_admin:
            bot.send_message(chat_id=message.chat.id, text="❌ Только главный админ может загружать промокоды файлами")
            del promocode_state[message.chat.id]
            return True

        # Загружаем файл
        if not getattr(message, 'document', None):
            return False
        file_id = message.document.file_id
        try:
            file_info = bot.get_file(file_id)
            file_bytes = bot.download_file(file_info.file_path)
        except Exception as e:
            logger.error(f"Не удалось скачать файл промокодов: {e}")
            bot.send_message(chat_id=message.chat.id, text="❌ Не удалось скачать файл. Попробуйте снова.")
            return True

        # Читаем текст
        content = None
        for enc in ("utf-8", "utf-16", "cp1251", "iso-8859-1"):
            try:
                content = file_bytes.decode(enc)
                break
            except Exception:
                continue
        if content is None:
            bot.send_message(chat_id=message.chat.id, text="❌ Не удалось определить кодировку файла.")
            return True

        lines = [line.strip().upper() for line in content.splitlines() if line.strip()]
        if not lines:
            bot.send_message(chat_id=message.chat.id, text="❌ Файл пустой или не содержит промокодов.")
            return True

        created_count = 0
        skipped_count = 0
        for code in lines:
            if len(code) > 50:
                skipped_count += 1
                continue
            try:
                promo, created = PromoCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'created_by': user,
                        'is_active': True,
                        'is_used': False,
                        'category': state.get('category')
                    }
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Ошибка создания промокода {code}: {e}")
                skipped_count += 1

        # Обновляем состояние для запроса инструкций
        promocode_state[message.chat.id]["awaiting_promocodes"] = False
        promocode_state[message.chat.id]["awaiting_instruction"] = True
        promocode_state[message.chat.id]["created_count"] = created_count
        promocode_state[message.chat.id]["skipped_count"] = skipped_count

        # Запрашиваем инструкции
        result_text = f"✅ Файл обработан:\n"
        result_text += f"• Создано промокодов: {created_count}\n"
        if skipped_count:
            result_text += f"• Пропущено: {skipped_count}\n"
        result_text += "\n💡 Инструкции можно добавить в админ-панели Django."
        
        # Удаляем состояние
        del promocode_state[message.chat.id]
        
        bot.send_message(chat_id=message.chat.id, text=result_text, reply_markup=get_promocode_menu_markup())
        return True
    except Exception as e:
        logger.error(f"Ошибка в handle_promocode_document: {e}")
        if message.chat.id in promocode_state:
            del promocode_state[message.chat.id]
        bot.send_message(chat_id=message.chat.id, text="Произошла ошибка при обработке файла.")
        return True


def promocode_list(call: CallbackQuery) -> None:
    """Показывает список промокодов"""
    try:
        from bot.models import OwnerSettings
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner_db = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(call.message.chat.id)
        is_owner = is_owner_db or is_owner_env
        
        if not user.is_admin and not is_owner:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        
        # Получаем последние 10 промокодов
        promocodes = PromoCode.objects.select_related('category').all()[:10]
        
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
        is_owner_db = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(call.message.chat.id)
        is_owner = is_owner_db or is_owner_env
        
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
        
        detail_text += f"\n📅 Созден: {promo.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        if promo.category:
            detail_text += f"🏷 Категория: {promo.category.name}\n"
        
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
    """Пользователь выбирает категорию, затем получает промокод"""
    try:
        # Удаляем предыдущее сообщение (может быть инструкция)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass  # Игнорируем ошибку, если не можем удалить
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        
        # Получаем все активные категории (независимо от статуса промокодов)
        all_categories = PromoCodeCategory.objects.filter(
            is_active=True
        ).order_by('name')
        
        if not all_categories.exists():
            bot.send_message(
                chat_id=call.message.chat.id,
                text="😔 К сожалению, сейчас нет доступных категорий промокодов.",
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "Нет доступных категорий")
            return
        
        bot.send_message(
            chat_id=call.message.chat.id,
            text="🎁 Выберите категорию подарка:",
            reply_markup=get_categories_markup(all_categories, prefix="get_promocode_cat", back_callback="back_to_main")
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в get_user_promocode: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def promocode_select_category(call: CallbackQuery) -> None:
    """Обработчик выбора категории для ввода текстом"""
    try:
        from bot.models import OwnerSettings
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        if not is_owner and not user.is_super_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id, is_active=True)
        promocode_state[call.message.chat.id] = {"awaiting_promocodes": True, "category": category}
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"➕ Добавление промокодов\n\n"
                f"Категория: {category.name}\n\n"
                "Отправьте промокоды одним сообщением:\n"
                "• Один промокод в строке\n"
                "• Или несколько промокодов, каждый с новой строки\n\n"
                "Пример:\n"
                "ZZ321D\n"
                "QEWCZ21\n"
                "ZXZCSED32"
            ),
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("⬅️ Назад", callback_data=f"promocode_back_to_category_{category.id}")
            )
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в promocode_select_category: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


def promocode_select_category_file(call: CallbackQuery) -> None:
    """Обработчик выбора категории для загрузки промокодов файлом"""
    try:
        from bot.models import OwnerSettings
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner_db = OwnerSettings.objects.filter(
            owner_telegram_id=call.message.chat.id,
            is_active=True
        ).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(call.message.chat.id)
        is_owner = is_owner_db or is_owner_env
        if not is_owner and not user.is_super_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id, is_active=True)
        promocode_state[call.message.chat.id] = {"awaiting_promocodes": True, "category": category}
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"📄 Загрузка промокодов файлом\n\n"
                f"Категория: {category.name}\n\n"
                "Прикрепите .txt файл, в котором каждый промокод на новой строке."
            ),
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("⬅️ Назад", callback_data=f"promocode_back_to_category_{category.id}")
            )
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в promocode_select_category_file: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


def promocode_choose_actions(call: CallbackQuery) -> None:
    """После выбора категории показать две кнопки: текстом или файлом"""
    try:
        from bot.models import OwnerSettings
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner_db = OwnerSettings.objects.filter(owner_telegram_id=call.message.chat.id, is_active=True).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(call.message.chat.id)
        is_owner = is_owner_db or is_owner_env
        if not is_owner and not user.is_super_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id, is_active=True)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Категория: {category.name}\nВыберите способ загрузки:",
            reply_markup=get_promocode_category_actions_markup(category.id, back_callback="promocode_add")
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в promocode_choose_actions: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


def promocode_back_to_category(call: CallbackQuery) -> None:
    """Кнопка назад из экранов загрузки (текст/файл) к выбору способа"
    """
    try:
        from bot.models import OwnerSettings
        user = User.objects.get(telegram_id=call.message.chat.id)
        is_owner_db = OwnerSettings.objects.filter(owner_telegram_id=call.message.chat.id, is_active=True).exists()
        is_owner_env = str(getattr(settings, 'OWNER_ID', '')).strip() == str(call.message.chat.id)
        is_owner = is_owner_db or is_owner_env
        if not is_owner and not user.is_super_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Категория: {category.name}\nВыберите способ загрузки:",
            reply_markup=get_promocode_category_actions_markup(category.id, back_callback="promocode_add")
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в promocode_back_to_category: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

def user_select_category(call: CallbackQuery) -> None:
    """Пользователь выбрал категорию - показываем кнопку 'Получить промокод'"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id, is_active=True)
        
        # Проверяем, не получал ли пользователь уже промокод из этой категории
        if not user.received_promocodes_by_category:
            user.received_promocodes_by_category = {}
        
        if str(cat_id) in user.received_promocodes_by_category:
            # Удаляем старое сообщение (список категорий) перед показом информации о полученном промокоде
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass  # Игнорируем ошибку, если не можем удалить
            
            # Показываем полученный промокод + кнопки инструкция и назад
            received_promo = user.received_promocodes_by_category[str(cat_id)]
            
            text = f"🎁 Категория: {category.name}\n\n"
            text += f"🎫 **Ваш промокод: `{received_promo}`**\n\n"
            text += "📋 Дополнительные действия:"
            
            # Проверяем наличие файла инструкции для отображения кнопки
            has_instruction_file = bool(category.instruction_file)
            
            # Создаем клавиатуру с кнопками
            from bot.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            
            # Кнопка инструкции (если есть файл)
            if has_instruction_file:
                markup.add(InlineKeyboardButton("📋 Инструкция", callback_data=f"get_instruction_{cat_id}"))
            
            markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            # Отправляем новое сообщение (предыдущее уже удалено)
            bot.send_message(
                chat_id=call.message.chat.id,
                text=text,
                parse_mode='Markdown',
                reply_markup=markup
            )
            
            bot.answer_callback_query(call.id, "Промокод уже получен")
            return
        
        available_promo = PromoCode.objects.filter(
            is_active=True,
            is_used=False,
            category=category
        ).first()
        if not available_promo:
            # Удаляем старое сообщение (список категорий) перед показом сообщения об отсутствии промокодов
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass  # Игнорируем ошибку, если не можем удалить
            
            # Отправляем новое сообщение
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"😔 К сожалению, в категории '{category.name}' пока нет доступных промокодов.\n\nСледите за нашими обновлениями!",
                reply_markup=back_to_main_markup
            )
            bot.answer_callback_query(call.id, "Нет доступных промокодов в этой категории")
            return
        
        # Проверяем наличие файла инструкции для отображения соответствующих кнопок
        has_instruction_file = bool(category.instruction_file)
        
        # Показываем информацию о промокоде и доступных действиях
        text = f"🎁 Категория: {category.name}\n\n"
        text += f"🌟 Доступен промокод!\n\n"
        
        if has_instruction_file:
            text += "📋 Доступные действия:"
            text += "\n• Получить промокод"
            text += "\n• Посмотреть файл с инструкциями"
        else:
            text += "Выберите действие ниже:"
        
        # Создаем клавиатуру с тремя кнопками
        from bot.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
        
        # Кнопка получения промокода (всегда доступна)
        markup.add(InlineKeyboardButton("🎯 Получить промокод", callback_data=f"claim_promocode_{cat_id}"))
        
        # Кнопка инструкции (если есть файл)
        if has_instruction_file:
            markup.add(InlineKeyboardButton("📋 Инструкция", callback_data=f"get_instruction_{cat_id}"))
        
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        # Удаляем старое сообщение (список категорий) перед показом информации о доступном промокоде
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass  # Игнорируем ошибку, если не можем удалить
        
        # Отправляем новое сообщение
        bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в user_select_category: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


def notify_admin_promocodes_shortage(category):
    """Отправляет уведомление главному админу о заканчивающихся промокодах"""
    try:
        from bot.models import OwnerSettings
        
        # Получаем главного админа (OwnerSettings)
        owner_settings = OwnerSettings.objects.filter(is_active=True).first()
        admin_user = User.objects.filter(is_super_admin=True).first()
        
        owner_id = None
        if owner_settings:
            owner_id = owner_settings.owner_telegram_id
        elif admin_user:
            owner_id = admin_user.telegram_id
        
        if not owner_id:
            logger.error("Не найден главный админ для отправки уведомления")
            return
        
        notification_text = f"⚠️ **Предупреждение о промокодах**\n\n"
        notification_text += f"📦 **Категория:** {category.name}\n"
        notification_text += f"📊 **Статус:** Промокоды в данной категории закончились\n\n"
        notification_text += "🔧 **Рекомендации:**\n"
        notification_text += "• Добавьте новые промокоды через админ-панель Telegram\n"
        notification_text += "• Настройте инструкции в админ-панели Django\n"
        notification_text += "• Проверьте статус других категорий\n\n"
        notification_text += "📝 Время: " + timezone.now().strftime("%d.%m.%Y %H:%M")
        
        bot.send_message(
            chat_id=owner_id,
            text=notification_text,
            parse_mode='Markdown'
        )
        logger.info(f"Отправлено уведомление главному админу о заканчивании промокодов в категории {category.name}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления об окончании промокодов: {e}")


def claim_promocode(call: CallbackQuery) -> None:
    """Обработчик получения промокода пользователем с инструкциями"""
    try:
        logger.info(f"[DEBUG] claim_promocode вызвана с {call.data}")
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id, is_active=True)
        
        logger.info(f"[DEBUG] Получаем промокод для категории: {category.name}")
        
        # Получаем доступный промокод
        available_promo = PromoCode.objects.filter(
            is_active=True,
            is_used=False,
            category=category
        ).first()
        
        if not available_promo:
            # Проверяем, есть ли еще промокоды в категории или они действительно закончились
            remaining_promos = PromoCode.objects.filter(
                is_active=True,
                is_used=False,
                category=category
            ).count()
            
            if remaining_promos == 0:
                # Уведомляем главного админа
                notify_admin_promocodes_shortage(category)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"😔 К сожалению, промокод в категории '{category.name}' больше недоступен.\n\nВозможно, он был уже израсходован другим пользователем.",
                reply_markup=back_to_main_markup
            )
            bot.answer_callback_query(call.id, "Промокод больше недоступен")
            return
        
        promo_code = available_promo.code
        instruction = category.instruction
        
        # Помечаем промокод как использованный
        available_promo.is_used = True
        available_promo.save()
        
        # Проверяем, сколько промокодов осталось после использования
        remaining_count = PromoCode.objects.filter(
            is_active=True,
            is_used=False,
            category=category
        ).count()
        
        # Если остался последний промокод, уведомляем админа
        if remaining_count == 1:
            notify_admin_promocodes_shortage(category)
        
        # Сохраняем в пользователе
        if not user.received_promocodes_by_category:
            user.received_promocodes_by_category = {}
        user.received_promocodes_by_category[str(cat_id)] = promo_code
        user.save()
        
        # Формируем сообщение с промокодом и инструкциями
        received_text = f"🎉 Поздравляем! Вы получили промокод в категории '{category.name}'!\n\n"
        received_text += f"🎫 **Ваш промокод: `{promo_code}`**\n\n"
        
        if instruction:
            received_text += f"📋 **Инструкция по применению:**\n{instruction}\n\n"
        else:
            received_text += "📋 **Инструкция:** Обратитесь в службу поддержки для получения инструкций по применению промокода.\n\n"
        
        # Показываем все полученные промокоды пользователя
        if len(user.received_promocodes_by_category) > 1:
            received_text += "🎁 **Ваши полученные промокоды:**\n"
            for cat_id_str, promocode in user.received_promocodes_by_category.items():
                try:
                    cat = PromoCodeCategory.objects.get(id=int(cat_id_str))
                    star = "⭐️" if str(cat_id) == str(cat_id_str) else "•"
                    received_text += f"{star} **{cat.name}**: `{promocode}`\n"
                except:
                    star = "⭐️" if str(cat_id) == str(cat_id_str) else "•"
                    received_text += f"{star} Промокод: `{promocode}`\n"
        
        received_text += "\n💡 **Помните:** Вы можете получить по одному промокоду в каждой категории!"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=received_text,
            parse_mode='Markdown',
            reply_markup=back_to_main_markup
        )
        bot.answer_callback_query(call.id, "🎁 Промокод получен!")
        
    except Exception as e:
        logger.error(f"Ошибка в claim_promocode: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")


def get_category_instruction(call: CallbackQuery) -> None:
    """Отправляет инструкцию пользователю - файл или текст"""
    try:
        logger.info(f"[DEBUG] get_category_instruction вызвана с {call.data}")
        
        # Удаляем старое сообщение перед показом инструкции
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass  # Игнорируем ошибку, если не можем удалить
        
        user = User.objects.get(telegram_id=call.message.chat.id)
        cat_id = int(call.data.split('_')[-1])
        category = PromoCodeCategory.objects.get(id=cat_id, is_active=True)
        
        logger.info(f"[DEBUG] Категория найдена: {category.name}")
        
        has_file = bool(category.instruction_file)
        
        logger.info(f"[DEBUG] has_file: {has_file}")
        
        instruction_sent = False
        
        # Если есть файл инструкции, отправляем его
        if has_file:
            try:
                logger.info(f"[DEBUG] Пытаемся отправить файл инструкции: {category.instruction_file.path}")
                
                # Отправляем файл и добавляем кнопку "Назад" под ним
                with open(category.instruction_file.path, 'rb') as file:
                    message_with_document = bot.send_document(
                        chat_id=call.message.chat.id,
                        document=file,
                        caption=f"📋 Инструкция для категории '{category.name}'"
                    )
                
                # Добавляем кнопку "Назад в главное меню"
                from bot.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="back_to_main"))
                
                bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=message_with_document.message_id,
                    reply_markup=markup
                )
                
                
                instruction_sent = True
                bot.answer_callback_query(call.id, "📋 Файл инструкции отправлен!")
                logger.info(f"[DEBUG] Файл инструкции отправлен успешно")
                
            except Exception as e:
                logger.error(f"[ERROR] Ошибка отправки файла инструкции: {e}")
                # Если файл не удалось отправить, показываем сообщение об ошибке
                # Добавляем кнопку "Назад в главное меню"
                from bot.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="back_to_main"))
                
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text="📋 Инструкция для данной категории временно недоступна.",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "❌ Инструкция недоступна")
                instruction_sent = True
        
        # Если нет файла инструкции
        if not instruction_sent:
            # Добавляем кнопку "Назад в главное меню"
            from bot.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="back_to_main"))
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text="📋 Инструкция для данной категории еще не добавлена администратором.",
                reply_markup=markup
            )
            bot.answer_callback_query(call.id, "❌ Инструкция не найдена")
            
    except Exception as e:
        logger.error(f"[ERROR] Ошибка в get_category_instruction: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")
