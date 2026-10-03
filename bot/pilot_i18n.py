COPY = {
    'ru': {
        'invite': '<b>Попробуйте Su-Tech на своём поле</b>\n\nПилот рассчитан на 5 дней. Вы вводите параметры реального участка, получаете расчёт и оцениваете, помог ли он принять решение. Оборудование покупать не нужно.\n\nУчаствуйте, если вы выращиваете культуры и отвечаете за полив. Нажимая кнопку, вы разрешаете сохранить Telegram ID, язык, факт участия и ваши оценки расчётов. Имя и телефон не запрашиваем. Через /pilot можно удалить эти данные.',
        'join': 'Участвовать в пилоте', 'joined': '<b>Вы участвуете в пилоте</b>\n\n1. Откройте приложение и укажите реальное поле.\n2. Получите расчёт и откройте «Почему так?».\n3. Под отчётом выберите «Полезно» или «Не помогло».\n4. Повторите расчёт в другой день, когда будете планировать полив.\n\nЗаписано оценок: {reviews}. Полезными отмечено: {useful}.\n\nВы решаете, применять ли рекомендацию на своём участке. Отзыв оценивает удобство расчёта; расход воды проверяется измерениями.',
        'leave': 'Удалить участие и отзывы', 'deleted': 'Участие и оценки удалены. Ваши поля и история расчётов сохранены.',
        'back': 'К приложению', 'useful': 'Полезно', 'unhelpful': 'Не помогло', 'thanks': 'Спасибо! Оценка сохранена.',
        'not_found': 'Этот расчёт недоступен. Выполните новый расчёт в приложении.', 'failed': 'Не удалось сохранить. Попробуйте ещё раз.',
        'private': 'Откройте личный чат с ботом.', 'deletePrompt':'Удалить участие в пилоте и все ваши оценки расчётов? Поля и история останутся.', 'confirmDelete':'Да, удалить', 'cancel':'Отмена',
    },
    'kz': {
        'invite': '<b>Su-Tech-ті өз алқабыңызда сынап көріңіз</b>\n\nПилот 5 күнге арналған. Нақты учаскенің параметрлерін енгізіп, есеп аласыз және оның шешім қабылдауға көмектескенін бағалайсыз. Жабдық сатып алу қажет емес.\n\nДақыл өсіріп, суаруға жауап берсеңіз, қатыса аласыз. Батырманы басу арқылы Telegram ID, тіл, қатысу фактісі және есеп бағаларын сақтауға келісесіз. Аты-жөніңіз бен телефон сұралмайды. /pilot арқылы осы деректерді жоя аласыз.',
        'join': 'Пилотқа қатысу', 'joined': '<b>Сіз пилотқа қатысып жатырсыз</b>\n\n1. Қолданбаны ашып, нақты алқапты белгілеңіз.\n2. Есеп алып, «Неге бұлай?» түсіндірмесін ашыңыз.\n3. Есеп астында «Пайдалы» немесе «Көмектеспеді» таңдаңыз.\n4. Суару жоспарлағанда басқа күні есепті қайталаңыз.\n\nСақталған бағалар: {reviews}. Пайдалы деп белгіленгені: {useful}.\n\nҰсынысты қолдану туралы шешімді өзіңіз қабылдайсыз. Пікір есептің ыңғайлылығын бағалайды; су шығыны өлшеумен тексеріледі.',
        'leave': 'Қатысу мен пікірлерді жою', 'deleted': 'Қатысу мен бағалар жойылды. Алқаптар мен есеп тарихы сақталды.',
        'back': 'Қолданбаға өту', 'useful': 'Пайдалы', 'unhelpful': 'Көмектеспеді', 'thanks': 'Рақмет! Баға сақталды.',
        'not_found': 'Бұл есеп қолжетімсіз. Қолданбада жаңа есеп жасаңыз.', 'failed': 'Сақтау мүмкін болмады. Қайталап көріңіз.',
        'private': 'Ботпен жеке чатты ашыңыз.', 'deletePrompt':'Пилотқа қатысуды және барлық есеп бағаларын жою керек пе? Алқаптар мен тарих сақталады.', 'confirmDelete':'Иә, жою', 'cancel':'Болдырмау',
    },
    'en': {
        'invite': '<b>Try Su-Tech on your own field</b>\n\nThe pilot runs for 5 days. Enter a real plot, receive a calculation and rate whether it helped your decision. No equipment purchase is required.\n\nJoin if you grow crops and manage irrigation. By pressing the button, you agree to save your Telegram ID, language, participation and report ratings. We do not request your name or phone. Use /pilot to delete this data.',
        'join': 'Join the pilot', 'joined': '<b>You have joined the pilot</b>\n\n1. Open the app and enter your real field.\n2. Get a calculation and open “Why this result?”.\n3. Choose “Helpful” or “Not helpful” below the report.\n4. Repeat on another day when planning irrigation.\n\nRatings saved: {reviews}. Marked helpful: {useful}.\n\nYou decide whether to apply a recommendation on your field. Feedback measures the usefulness of a calculation; water consumption requires measurements.',
        'leave': 'Delete participation and ratings', 'deleted': 'Participation and ratings deleted. Your fields and calculation history remain.',
        'back': 'Open the app', 'useful': 'Helpful', 'unhelpful': 'Not helpful', 'thanks': 'Thank you! Rating saved.',
        'not_found': 'This calculation is unavailable. Run a new calculation in the app.', 'failed': 'Could not save. Please try again.',
        'private': 'Open a private chat with the bot.', 'deletePrompt':'Delete pilot participation and all your report ratings? Fields and history will remain.', 'confirmDelete':'Yes, delete', 'cancel':'Cancel',
    },
}


def pilot_text(lang, key, **values):
    return COPY.get(lang,COPY['ru'])[key].format(**values)
