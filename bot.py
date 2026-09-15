import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TOKEN = "ur token"
SCHEDULE_CHANNEL_ID = 1234  # Укажите ID канала
ALLOWED_ROLE_ID = 23131     # ID роли, которой разрешено управлением ивентами

EVENT_BANNERS = {
    "Speed dating": "https://cdn.discordapp.com/attachments/1457052775472169198/1548622570163666954/7376c626-47cf-4033-8724-3b3fe417f421.png",
    "Mafia": "https://cdn.discordapp.com/attachments/1457052775472169198/1548617332442669107/d9b52d6b-e18e-473a-a47b-bd4df36cab6e.png",
    "Films": "https://cdn.discordapp.com/attachments/1457052775472169198/1548621095803035718/1e5be2b1-1702-4729-b7a1-eca90a390f03.png",
    "Hike": "https://cdn.discordapp.com/attachments/1457052775472169198/1548619040677961758/15834961-fdb1-4946-b010-64a2dcaf9428.png",
    "Bunker": "https://cdn.discordapp.com/attachments/1457052775472169198/1548623379668664431/8d6d8e3e-5ca0-4528-a4de-03c1f0983cbb.png",
    "Talents": "https://cdn.discordapp.com/attachments/1457052775472169198/1548624049821843497/26dbe1b6-434b-42a4-8b07-b59b6ccaa531.png",
    "Karaoke": "https://cdn.discordapp.com/attachments/1457052775472169198/1548624440768598027/fa56da0f-0f8a-4b4a-8abb-bba99800e1e0.png",
    "Tournament": "https://cdn.discordapp.com/attachments/1457052775472169198/1548624831392780348/5c8d3ce3-25ae-4d75-950e-8df68481b107.png"
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- МОДАЛЬНОЕ ОКНО ДЛЯ ПЕРЕНОСА ВРЕМЕНИ ---
class RescheduleModal(discord.ui.Modal, title="Перенос времени ивента"):
    new_time = discord.ui.TextInput(
        label="Новое время (МСК)",
        placeholder="19:30",
        min_length=5,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hour, minute = map(int, self.new_time.value.split(':'))
            msk_tz = ZoneInfo("Europe/Moscow")
            now_msk = datetime.now(msk_tz)
            
            event_time = now_msk.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if event_time < now_msk:
                event_time += timedelta(days=1)

            unix_timestamp = int(event_time.timestamp())
            
            # Обновление эмбеда
            embed = interaction.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if "Время" in field.name:
                    embed.set_field_at(
                        i, 
                        name="🕒 Время (Перенесено)", 
                        value=f"<t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)", 
                        inline=True
                    )
                    break
                    
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message("✅ Время ивента успешно перенесено!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Неверный формат времени! Используйте `ЧЧ:ММ`.", ephemeral=True)

# --- ПАНЕЛЬ КНОПОК ПОД ОБЪЯВЛЕНИЕМ ---
class EventControlView(discord.ui.View):
    def __init__(self, host_id: int):
        super().__init__(timeout=None)
        self.host_id = host_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Проверка наличие нужной роли у нажавшего
        has_role = any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles)
        if not has_role and interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ У вас нет прав для управления этим ивентом!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Перенести", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def reschedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RescheduleModal())

    @discord.ui.button(label="Отменить ивент", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.dark_red()
        embed.title = f"❌ [ОТМЕНЕН] {embed.title}"
        
        # Отключаем все кнопки после отмены
        for child in self.children:
            child.disabled = True
            
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("🗑️ Ивент отменен.", ephemeral=True)

# --- КОМАНДА АНОНСА ---
event_choices = [
    app_commands.Choice(name="🎥 Просмотр фильмов", value="Films"),
    app_commands.Choice(name="💘 Быстрые Свидания", value="Speed dating"),
    app_commands.Choice(name="🗻 Поход", value="Hike"),
    app_commands.Choice(name="🕵️ Мафия", value="Mafia"),
    app_commands.Choice(name="☢️ Бункер", value="Bunker"),
    app_commands.Choice(name="⭐ Шоу талантов", value="Talents"),
    app_commands.Choice(name="🎤 Караоке", value="Karaoke"),
    app_commands.Choice(name="🎙️ Сходка / Общий сбор", value="Meeting"),
    app_commands.Choice(name="🏆 Турнир", value="Tournament")
]

@bot.event
async def on_ready():
    print(f'Бот {bot.user} успешно запущен!')
    try:
        synced = await bot.tree.sync()
        print(f'Синхронизировано {len(synced)} слеш-команд.')
    except Exception as e:
        print(f'Ошибка при синхронизации команд: {e}')

@bot.tree.command(name="announce", description="Сделать объявление об ивенте с интерактивной панелью")
@app_commands.describe(
    event_type="Выберите тип ивента",
    time_str="Время проведения (в МСК). Формат: ЧЧ:ММ, например 18:30",
    host="Ведущий ивента",
    info_text="Описание правил или условий ивента"
)
@app_commands.choices(event_type=event_choices)
async def announce(
    interaction: discord.Interaction, 
    event_type: app_commands.Choice[str], 
    time_str: str, 
    host: discord.Member = None,
    info_text: str = "Участников собирают для проведения ивента. Правила и детали уточняйте в инфо-канале."
):
    if host is None:
        host = interaction.user

    try:
        hour, minute = map(int, time_str.split(':'))
        msk_tz = ZoneInfo("Europe/Moscow")
        now_msk = datetime.now(msk_tz)
        
        event_time = now_msk.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if event_time < now_msk:
            event_time += timedelta(days=1)

        unix_timestamp = int(event_time.timestamp())
        
    except ValueError:
        await interaction.response.send_message("❌ Неверный формат времени! Используйте `ЧЧ:ММ`.", ephemeral=True)
        return

    channel = bot.get_channel(SCHEDULE_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("❌ Канал расписания не найден.", ephemeral=True)
        return

    banner_url = EVENT_BANNERS.get(event_type.value, None)

    embed = discord.Embed(
        title=f"•  {event_type.name.split(' ', 1)[1]}",
        color=discord.Color.from_rgb(139, 0, 32)
    )
    
    if banner_url:
        embed.set_image(url=banner_url)

    embed.add_field(name="Описание и правила", value=f"{info_text}", inline=False)
    embed.add_field(name="🕒 Время", value=f"<t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)", inline=True)
    embed.add_field(name="👤 Ведущий", value=f"{host.mention}", inline=True)
    embed.set_footer(text="Подробности: инфо-канал доступен на сервере.")

    # Создание панели с кнопками для управления
    view = EventControlView(host_id=host.id)

    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ Карточка ивента опубликована в {channel.mention}!", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)