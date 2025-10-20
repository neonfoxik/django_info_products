from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot, logger
from bot.models import User, goods_category, goods, WarrantyIssue, WarrantyRequest, Support, WarrantyQuestion, WarrantyAnswer
from bot.handlers.support import warranty_to_support_context
from bot.keyboards import get_support_platform_markup


# Состояния для работы с гарантией
warranty_state = {}
 # Состояние опроса вопросов перед выбором платформы: по chat_id храним прогресс
warranty_qna_state = {}


def _start_warranty_questionnaire(user: User, warranty_request: WarrantyRequest, chat_id: int) -> None:
    """Запускает опрос активных вопросов. Если вопросов нет — сразу переводит к выбору платформы."""
    questions = list(WarrantyQuestion.objects.filter(is_active=True).order_by('order','id'))
    if not questions:
        _finish_questionnaire_and_ask_platform(user, warranty_request, chat_id)
        return
    warranty_qna_state[chat_id] = {
        'request_id': warranty_request.id,
        'question_ids': [q.id for q in questions],
        'index': 0,
    }
    first_q = questions[0]
    bot.send_message(chat_id=chat_id, text=f"❓ {first_q.text}")


def _finish_questionnaire_and_ask_platform(user: User, warranty_request: WarrantyRequest, chat_id: int) -> None:
    """Формирует контекст для поддержки с ответами и показывает выбор платформы."""
    details = [
        "Пользователь оформляет гарантийный случай.",
    ]
    try:
        if warranty_request.product:
            details.append(f"Товар: {warranty_request.product.name}")
        if warranty_request.issue:
            details.append(f"Проблема: {warranty_request.issue.title}")
        if warranty_request.custom_issue_description:
            details.append(f"Описание: {warranty_request.custom_issue_description}")
        # Добавляем ответы на вопросы
        answers = WarrantyAnswer.objects.filter(request=warranty_request).select_related('question').order_by('created_at')
        if answers.exists():
            details.append("\nОтветы на уточняющие вопросы:")
            for a in answers:
                q_text = a.question.text if a.question_id else "Вопрос"
                details.append(f"- {q_text}\n  Ответ: {a.answer_text}")
    except Exception:
        pass
    warranty_to_support_context[chat_id] = {
        'text': "\n".join(details)
    }
    bot.send_message(
        chat_id=chat_id,
        text=(
            "Выберите платформу, где была покупка, чтобы открыть чат поддержки."
        ),
        reply_markup=get_support_platform_markup()
    )


def process_warranty_questionnaire_answer(message: Message) -> bool:
    """Обрабатывает ответ пользователя на текущий вопрос анкеты. Возвращает True, если обработано."""
    chat_id = message.chat.id
    state = warranty_qna_state.get(chat_id)
    if not state:
        return False
    try:
        user = User.objects.get(telegram_id=chat_id)
        warranty_request = WarrantyRequest.objects.get(id=state['request_id'])
        q_ids = state['question_ids']
        idx = state['index']
        # Текущий вопрос
        current_q_id = q_ids[idx]
        question = WarrantyQuestion.objects.get(id=current_q_id)
        # Сохраняем ответ
        WarrantyAnswer.objects.update_or_create(
            request=warranty_request,
            question=question,
            defaults={'answer_text': message.text or ''}
        )
        # Переходим к следующему вопросу
        idx += 1
        if idx < len(q_ids):
            state['index'] = idx
            next_q = WarrantyQuestion.objects.get(id=q_ids[idx])
            bot.send_message(chat_id=chat_id, text=f"❓ {next_q.text}")
            return True
        else:
            # Завершаем опрос
            warranty_qna_state.pop(chat_id, None)
            _finish_questionnaire_and_ask_platform(user, warranty_request, chat_id)
            return True
    except Exception as e:
        logger.error(f"Ошибка обработки ответа анкеты гарантии: {e}")
        # На всякий случай завершим опрос и продолжим
        try:
            warranty_qna_state.pop(chat_id, None)
            user = User.objects.get(telegram_id=chat_id)
            warranty_request = WarrantyRequest.objects.filter(user=user).order_by('-created_at').first()
            if warranty_request:
                _finish_questionnaire_and_ask_platform(user, warranty_request, chat_id)
        except Exception:
            pass
        return True


def warranty_start(call: CallbackQuery) -> None:
    """Начало процесса обращения по гарантии - выбор категории товара"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        
        # Получаем все активные категории товаров
        categories = goods_category.objects.all()
        
        if not categories.exists():
            # Удаляем старое сообщение
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text="😔 К сожалению, категории товаров не найдены.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
                )
            )
            bot.answer_callback_query(call.id)
            return
        
        # Создаем клавиатуру с категориями
        markup = InlineKeyboardMarkup()
        for category in categories:
            # Проверяем, есть ли активные товары в категории
            products_count = goods.objects.filter(
                parent_category=category,
                is_active=True
            ).count()
            
            if products_count > 0:
                markup.add(
                    InlineKeyboardButton(
                        f"📦 {category.name} ({products_count})",
                        callback_data=f"warranty_category_{category.id}"
                    )
                )
        
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем новое сообщение
        bot.send_message(
            chat_id=call.message.chat.id,
            text="🔧 *Обращение по гарантии*\n\n"
                 "Выберите категорию вашего товара:",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_start: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def warranty_select_category(call: CallbackQuery) -> None:
    """Пользователь выбрал категорию - показываем товары"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        category_id = int(call.data.split('_')[-1])
        category = goods_category.objects.get(id=category_id)
        
        # Получаем все активные товары в категории
        products = goods.objects.filter(
            parent_category=category,
            is_active=True
        )
        
        if not products.exists():
            # Удаляем старое сообщение
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"😔 В категории '{category.name}' нет доступных товаров.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("⬅️ Назад", callback_data="warranty_start")
                )
            )
            bot.answer_callback_query(call.id)
            return
        
        # Создаем клавиатуру с товарами
        markup = InlineKeyboardMarkup()
        for product in products:
            # Проверяем, есть ли для товара типичные проблемы
            issues_count = WarrantyIssue.objects.filter(
                product=product,
                is_active=True
            ).count()
            
            markup.add(
                InlineKeyboardButton(
                    f"📱 {product.name}" + (f" ({issues_count})" if issues_count > 0 else ""),
                    callback_data=f"warranty_product_{product.id}"
                )
            )
        
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="warranty_start"))
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем новое сообщение
        bot.send_message(
            chat_id=call.message.chat.id,
            text=f"🔧 *Обращение по гарантии*\n\n"
                 f"Категория: *{category.name}*\n\n"
                 f"Выберите ваш товар:",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_select_category: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def warranty_select_product(call: CallbackQuery) -> None:
    """Пользователь выбрал товар - показываем типичные проблемы"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        product_id = int(call.data.split('_')[-1])
        product = goods.objects.get(id=product_id)
        
        # Создаем или получаем запрос по гарантии
        warranty_request, created = WarrantyRequest.objects.get_or_create(
            user=user,
            status='selecting_issue',
            defaults={'product': product}
        )
        
        if not created:
            warranty_request.product = product
            warranty_request.status = 'selecting_issue'
            warranty_request.save()
        
        # Получаем типичные проблемы для товара
        issues = WarrantyIssue.objects.filter(
            product=product,
            is_active=True
        ).order_by('order', 'title')
        
        # Создаем клавиатуру с проблемами
        markup = InlineKeyboardMarkup()
        
        if issues.exists():
            for issue in issues:
                markup.add(
                    InlineKeyboardButton(
                        f"⚠️ {issue.title}",
                        callback_data=f"warranty_issue_{issue.id}"
                    )
                )
        
        # Всегда добавляем кнопку "Другое"
        markup.add(
            InlineKeyboardButton(
                "❓ Другое",
                callback_data=f"warranty_other_{product_id}"
            )
        )
        markup.add(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"warranty_category_{product.parent_category.id}"
            )
        )
        
        text = f"🔧 *Обращение по гарантии*\n\n"
        text += f"Товар: *{product.name}*\n\n"
        text += "Выберите, что у вас сломалось:"
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем новое сообщение с перечнем проблем
        bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_select_product: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def warranty_select_issue(call: CallbackQuery) -> None:
    """Пользователь выбрал проблему - показываем решение"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        issue_id = int(call.data.split('_')[-1])
        issue = WarrantyIssue.objects.get(id=issue_id)
        
        # Обновляем запрос по гарантии
        warranty_request = WarrantyRequest.objects.filter(
            user=user,
            status='selecting_issue'
        ).first()
        
        if warranty_request:
            warranty_request.issue = issue
            warranty_request.status = 'got_solution'
            warranty_request.save()
        else:
            # Создаем новый запрос
            warranty_request = WarrantyRequest.objects.create(
                user=user,
                product=issue.product,
                issue=issue,
                status='got_solution'
            )
        
        # Клавиатура с кнопками
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Помогло", callback_data=f"warranty_helped_{warranty_request.id}"),
            InlineKeyboardButton("❌ Не помогло", callback_data=f"warranty_not_helped_{warranty_request.id}")
        )
        markup.add(
            InlineKeyboardButton("⬅️ Назад", callback_data=f"warranty_product_{issue.product.id}")
        )
        
        # Формируем текст
        text = f"🔧 *Решение проблемы*\n\n"
        text += f"Товар: *{issue.product.name}*\n"
        text += f"Проблема: *{issue.title}*\n\n"
        
        # Проверяем, есть ли текстовое решение
        has_text = bool(issue.solution_template and issue.solution_template.strip())
        has_file = bool(issue.solution_file)
        
        if has_text:
            text += f"📝 *Инструкция:*\n\n{issue.solution_template}\n\n"
        
        if has_file:
            text += "📎 *Файл с инструкцией прикреплен ниже*\n\n"
        
        if not has_text and not has_file:
            text += "ℹ️ Решение временно недоступно. Обратитесь к менеджеру.\n\n"
        
        text += "Помогло ли это решение?"
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем текст
        msg = bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        # Если есть файл, отправляем его
        if has_file:
            try:
                with open(issue.solution_file.path, 'rb') as file:
                    bot.send_document(
                        chat_id=call.message.chat.id,
                        document=file,
                        caption=f"📋 Инструкция: {issue.title}"
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки файла решения: {e}")
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_select_issue: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def warranty_helped(call: CallbackQuery) -> None:
    """Решение помогло"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        request_id = int(call.data.split('_')[-1])
        
        warranty_request = WarrantyRequest.objects.get(id=request_id)
        warranty_request.solution_helped = True
        warranty_request.status = 'closed'
        warranty_request.save()
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем новое сообщение
        bot.send_message(
            chat_id=call.message.chat.id,
            text="✅ *Отлично!*\n\n"
                 "Рады, что смогли помочь! 😊\n\n"
                 "Если возникнут другие вопросы - обращайтесь!",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "Спасибо за обратную связь!")
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_helped: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def warranty_not_helped(call: CallbackQuery) -> None:
    """Решение не помогло - переводим на менеджера"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        request_id = int(call.data.split('_')[-1])
        
        warranty_request = WarrantyRequest.objects.get(id=request_id)
        warranty_request.solution_helped = False
        warranty_request.status = 'needs_manager'
        warranty_request.save()
        
        # Удаляем сообщение с решением/кнопками, которое сейчас висит
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        # Запускаем анкету вопросов перед переводом в поддержку
        try:
            _start_warranty_questionnaire(user, warranty_request, call.message.chat.id)
        except Exception as e:
            logger.error(f"Не удалось запустить опрос гарантий: {e}")

        # Готовим контекст для чата поддержки
        details = [
            "Пользователь перенаправлен из гарантийного потока.",
        ]
        try:
            if warranty_request.product:
                details.append(f"Товар: {warranty_request.product.name}")
            if warranty_request.issue:
                details.append(f"Проблема: {warranty_request.issue.title}")
            if warranty_request.custom_issue_description:
                details.append(f"Описание: {warranty_request.custom_issue_description}")
        except Exception:
            pass
        details.append("Статус: решение не помогло.")
        warranty_to_support_context[call.message.chat.id] = {
            'text': "\n".join(details)
        }

        # Выбор платформы покажем после завершения анкеты (_finish_questionnaire_and_ask_platform)
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_not_helped: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def warranty_other(call: CallbackQuery) -> None:
    """Пользователь выбрал "Другое" - переводим на менеджера"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        product_id = int(call.data.split('_')[-1])
        product = goods.objects.get(id=product_id)
        
        # Обновляем запрос по гарантии
        warranty_request = WarrantyRequest.objects.filter(
            user=user,
            status='selecting_issue'
        ).first()
        
        if warranty_request:
            warranty_request.custom_issue_description = "Другое (пользователь выбрал 'Другое')"
            warranty_request.status = 'needs_manager'
            warranty_request.save()
        else:
            warranty_request = WarrantyRequest.objects.create(
                user=user,
                product=product,
                custom_issue_description="Другое (пользователь выбрал 'Другое')",
                status='needs_manager'
            )
        
        # Удаляем текущее сообщение с проблемами/кнопками
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        # Запускаем анкету вопросов перед переводом в поддержку
        try:
            _start_warranty_questionnaire(user, warranty_request, call.message.chat.id)
        except Exception as e:
            logger.error(f"Не удалось запустить опрос гарантий: {e}")

        # Готовим контекст и старт поддержки
        details = [
            "Пользователь перенаправлен из гарантийного потока.",
            f"Товар: {product.name}",
            "Описание: Другое (пользователь выбрал 'Другое')",
            "Статус: нужен менеджер.",
        ]
        warranty_to_support_context[call.message.chat.id] = {
            'text': "\n".join(details)
        }

        # Выбор платформы покажем после завершения анкеты (_finish_questionnaire_and_ask_platform)
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в warranty_other: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")

