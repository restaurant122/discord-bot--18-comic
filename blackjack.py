import discord
from discord import app_commands
from discord.ext import commands
import random

# ==================== 模擬 AI 玩家類別 ====================
class AIBotPlayer:
    def __init__(self, name):
        self.id = random.randint(10000000, 99999999)
        self.display_name = name
        self.name = name
        self.mention = f"🤖 **{name}**"
        self.bot = True


# ==================== 3. 個人私密操作面板 (Ephemeral View) ====================
class PlayerControlView(discord.ui.View):
    def __init__(self, game_view, player_id):
        super().__init__(timeout=180)
        self.game_view = game_view
        self.player_id = player_id

    @discord.ui.button(label="要牌 (Hit)", style=discord.ButtonStyle.success, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("這不是你的操作面板！", ephemeral=True)
            return
        
        if self.game_view.game_over:
            await interaction.response.send_message("遊戲已經結束囉！", ephemeral=True)
            return

        current_user = self.game_view.players[self.game_view.current_player_index]
        if interaction.user.id != current_user.id:
            await interaction.response.send_message("目前還沒輪到你的回合！", ephemeral=True)
            return

        current_hand = self.game_view.hands[current_user.id]

        # 檢查是否已經達到 5 張牌上限
        if len(current_hand) >= 5:
            await interaction.response.send_message("⚠️ 抽牌上限為 **5張**！已自動為您強制停牌。", ephemeral=True)
            await self.game_view.next_turn()
            await self.game_view.update_public_message()
            return

        # 發牌
        card = self.game_view.draw_card()
        current_hand.append(card)
        score = self.game_view.calculate_score(current_hand)
        hand_len = len(current_hand)

        # 檢查是否達成 5 張牌 (五小龍) 或 爆牌
        if hand_len >= 5 and score <= 21:
            await interaction.response.send_message(f"🎉 恭喜達成 **5張牌上限（五小龍）**！系統已自動為您停牌。\n您的手牌: {self.game_view.format_hand(current_hand, hide_first=False)} (點數: {score})", ephemeral=True)
            await self.game_view.next_turn()
        elif score >= 21:
            await interaction.response.send_message(f"💥 哎呀，爆牌了！\n您的手牌: {self.game_view.format_hand(current_hand, hide_first=False)} (點數: {score})", ephemeral=True)
            await self.game_view.next_turn()
        else:
            await interaction.response.send_message(f"🃏 你抽到了 `{card['suit']}{card['rank']}`\n目前手牌: {self.game_view.format_hand(current_hand, hide_first=False)}\n目前點數: **{score} 點** (目前共 {hand_len} 張)", ephemeral=True)

        await self.game_view.update_public_message()

    @discord.ui.button(label="停牌 (Stand)", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("這不是你的操作面板！", ephemeral=True)
            return

        if self.game_view.game_over:
            await interaction.response.send_message("遊戲已經結束囉！", ephemeral=True)
            return

        current_user = self.game_view.players[self.game_view.current_player_index]
        if interaction.user.id != current_user.id:
            await interaction.response.send_message("目前還沒輪到你的回合！", ephemeral=True)
            return

        score = self.game_view.calculate_score(self.game_view.hands[current_user.id])
        await interaction.response.send_message(f"🛑 你選擇停牌。最終手牌點數為: **{score} 點**", ephemeral=True)
        
        await self.game_view.next_turn()
        await self.game_view.update_public_message()


# ==================== 2. 遊戲進行中的公開介面 (Game View) ====================
class BlackjackGameView(discord.ui.View):
    def __init__(self, bot, players, host_id, is_solo=False, channel=None):
        super().__init__(timeout=300)
        self.bot = bot
        self.players = players
        self.host_id = host_id
        self.is_solo = is_solo
        self.channel = channel
        self.hands = {p.id: [] for p in players}
        self.dealer_hand = []
        self.current_player_index = 0
        self.game_over = False
        self.message = None 
        
        self.initialize_deck()
        self.deal_initial_cards()
        self.update_main_buttons()

    def initialize_deck(self):
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.deck = [{'suit': s, 'rank': r} for s in suits for r in ranks]
        random.shuffle(self.deck)

    def draw_card(self):
        if not self.deck:
            self.initialize_deck()
        return self.deck.pop()

    def calculate_score(self, hand):
        score = 0
        aces = 0
        for card in hand:
            rank = card['rank']
            if rank in ['J', 'Q', 'K']:
                score += 10
            elif rank == 'A':
                aces += 1
                score += 11
            else:
                score += int(rank)
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    def deal_initial_cards(self):
        for p in self.players:
            self.hands[p.id].append(self.draw_card())
            self.hands[p.id].append(self.draw_card())
        self.dealer_hand.append(self.draw_card())
        self.dealer_hand.append(self.draw_card())

    def format_hand(self, hand, hide_first=False):
        if hide_first and len(hand) > 1:
            return f"🎴 [暗牌] " + " ".join([f"{c['suit']}{c['rank']}" for c in hand[1:]])
        return " ".join([f"{c['suit']}{c['rank']}" for c in hand])

    def get_unique_display_names(self):
        name_counts = {}
        for p in self.players:
            name = getattr(p, 'display_name', getattr(p, 'name', '玩家'))
            name_counts[name] = name_counts.get(name, 0) + 1
        
        seen = {}
        unique_names = {}
        for p in self.players:
            name = getattr(p, 'display_name', getattr(p, 'name', '玩家'))
            if name_counts[name] > 1:
                seen[name] = seen.get(name, 0) + 1
                unique_names[p.id] = f"{name}({seen[name]})"
            else:
                unique_names[p.id] = name
        return unique_names

    def update_main_buttons(self):
        self.clear_items()
        if not self.game_over:
            control_btn = discord.ui.Button(label="🎯 開啟我的手牌與操作面板", style=discord.ButtonStyle.primary, emoji="👁️")
            control_btn.callback = self.open_control_panel
            self.add_item(control_btn)
        else:
            again_btn = discord.ui.Button(label="🔄 再來一局 (重新開局)", style=discord.ButtonStyle.primary)
            again_btn.callback = self.play_again_callback
            self.add_item(again_btn)

    async def open_control_panel(self, interaction: discord.Interaction):
        player_obj = discord.utils.get(self.players, id=interaction.user.id)
        if not player_obj:
            await interaction.response.send_message("你並不是這局遊戲的參與者！", ephemeral=True)
            return
        
        score = self.calculate_score(self.hands[interaction.user.id])
        hand_str = self.format_hand(self.hands[interaction.user.id], hide_first=False)
        
        is_my_turn = (not self.game_over and self.players[self.current_player_index].id == interaction.user.id)
        turn_status = "✨ **目前輪到你的回合！** 請使用下方按鈕進行動作：" if is_my_turn else "⏳ 目前還沒輪到你的回合，您可以先查看手牌。"

        view = PlayerControlView(self, interaction.user.id) if is_my_turn else None
        
        await interaction.response.send_message(
            f"🔐 **【私密手牌面板】**\n你的手牌: {hand_str}\n點數總計: **{score} 點** (共 {len(self.hands[interaction.user.id])} 張牌)\n\n{turn_status}",
            view=view,
            ephemeral=True
        )

    def create_embed(self):
        embed = discord.Embed(title="🃏 21 點盲牌對戰進行中", color=discord.Color.green())
        names = self.get_unique_display_names()
        
        dealer_score = self.calculate_score(self.dealer_hand)
        
        if not self.game_over and len(self.dealer_hand) >= 2:
            dealer_public_display = f"🎴 [暗牌] " + " ".join([f"{c['suit']}{c['rank']}" for c in self.dealer_hand[1:]])
        else:
            dealer_public_display = self.format_hand(self.dealer_hand)

        dealer_status = ""
        if self.game_over:
            if dealer_score > 21:
                dealer_status = " 💥 爆牌!"
            elif dealer_score == 21:
                dealer_status = " ✨ 21點!"

        embed.add_field(
            name="🤖 莊家", 
            value=f"手牌: {dealer_public_display}\n點數: {dealer_score if self.game_over else '??'}{dealer_status}", 
            inline=False
        )

        for i, p in enumerate(self.players):
            hand = self.hands[p.id]
            score = self.calculate_score(hand)
            is_bust = score > 21
            is_five_cards = (len(hand) >= 5 and score <= 21)

            should_hide_first = not self.game_over and not is_bust
            hand_display = self.format_hand(hand, hide_first=should_hide_first)

            status = ""
            if is_bust:
                status = " 💥 爆牌!"
            elif is_five_cards:
                status = " 🐉 5張牌(自動21點)!"
            elif score == 21:
                status = " ✨ 21點!"
            
            is_turn = (i == self.current_player_index and not self.game_over)
            pointer = "▶️ **[思考中...]** " if is_turn else ""
            
            # 💡 修正：移除 is_turn 條件，確保在大廳中未結束/未爆牌前絕對不顯示個人點數（維持 ??）
            embed.add_field(
                name=f"{pointer}玩家: {names[p.id]} ({len(hand)}張牌)",
                value=f"手牌: {hand_display}\n點數: {score if (self.game_over or is_bust) else '??'}{status}",
                inline=False
            )

        if not self.game_over:
            current_user = self.players[self.current_player_index]
            embed.set_footer(text=f"目前輪到: {names[current_user.id]} 正在操作 (請點擊按鈕查看並操作)")
        else:
            embed.title = "🏆 21 點盲牌大對戰結算排行榜"
            embed.color = discord.Color.gold()
            
            dealer_bust = dealer_score > 21
            rank_data = []
            
            for p in self.players:
                hand = self.hands[p.id]
                score = self.calculate_score(hand)
                is_bust = score > 21
                is_five = (len(hand) >= 5 and score <= 21)
                
                if is_bust:
                    tier = 1
                    effective = -1
                elif is_five:
                    tier = 3
                    effective = 2000 + score
                else:
                    tier = 2
                    effective = score

                rank_data.append({
                    'player': p, 
                    'score': score, 
                    'is_bust': is_bust, 
                    'is_five': is_five,
                    'tier': tier,
                    'effective': effective
                })

            rank_data.sort(key=lambda x: (x['tier'], x['effective']), reverse=True)

            leaderboard_lines = []
            curr_rank = 1
            for idx, item in enumerate(rank_data):
                if idx > 0 and (item['tier'] < rank_data[idx - 1]['tier'] or item['effective'] < rank_data[idx - 1]['effective']):
                    curr_rank = idx + 1
                
                p_name = names[item['player'].id]
                score_str = f"{item['score']}點 ({len(self.hands[item['player'].id])}張)" if not item['is_bust'] else "爆牌 (💥)"
                
                if item['is_bust']:
                    desc = "❌ 淘汰 (爆牌)"
                elif item['is_five']:
                    desc = "🐲 五小龍神卡 (大於一切)"
                elif dealer_bust:
                    desc = "🎉 勝 (莊家爆牌)"
                elif item['score'] > dealer_score:
                    desc = "🎉 擊敗莊家"
                elif item['score'] == dealer_score:
                    desc = "🤝 平手"
                else:
                    desc = "💧 輸給莊家"

                leaderboard_lines.append(f"**第 {curr_rank} 名**: {p_name} — {score_str} [{desc}]")

            embed.add_field(name="📊 最終排行榜", value="\n".join(leaderboard_lines), inline=False)
            embed.set_footer(text="遊戲已結束！點擊下方按鈕可重新開局。")

        return embed

    async def update_public_message(self):
        if self.message and not self.game_over:
            try:
                await self.message.edit(embed=self.create_embed(), view=self)
            except discord.HTTPException:
                pass

    async def finalize_game(self):
        self.game_over = True
        self.update_main_buttons()
        if self.message:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
        if self.channel:
            self.message = await self.channel.send(embed=self.create_embed(), view=self)

    async def process_ai_turns_if_needed(self):
        while not self.game_over and self.current_player_index < len(self.players):
            current_user = self.players[self.current_player_index]
            
            if getattr(current_user, 'bot', False):
                while True:
                    hand = self.hands[current_user.id]
                    score = self.calculate_score(hand)
                    hand_len = len(hand)

                    if hand_len >= 5 or score >= 21:
                        break
                    
                    if score <= 11:
                        hit_chance = 1.0
                    elif score <= 14:
                        hit_chance = 0.75
                    elif score <= 17:
                        hit_chance = 0.40
                    else:
                        hit_chance = 0.15
                    
                    if random.random() < hit_chance:
                        self.hands[current_user.id].append(self.draw_card())
                    else:
                        break
                
                self.current_player_index += 1
                if self.current_player_index >= len(self.players):
                    while self.calculate_score(self.dealer_hand) < 17:
                        self.dealer_hand.append(self.draw_card())
                    await self.finalize_game()
                    break
            else:
                break

    async def next_turn(self):
        self.current_player_index += 1
        if self.current_player_index >= len(self.players):
            while self.calculate_score(self.dealer_hand) < 17:
                self.dealer_hand.append(self.draw_card())
            await self.finalize_game()
        else:
            await self.process_ai_turns_if_needed()

    async def play_again_callback(self, interaction: discord.Interaction):
        if self.is_solo:
            players = [interaction.user, AIBotPlayer("賭神小艾"), AIBotPlayer("牌局小助手")]
            new_game_view = BlackjackGameView(self.bot, players, interaction.user.id, is_solo=True, channel=interaction.channel)
            await new_game_view.process_ai_turns_if_needed()

            embed = new_game_view.create_embed()
            embed.title = "🃏 單人盲牌對戰模式"
            embed.description = "與 2 位 AI 玩家及 AI 莊家展開 21 點盲牌對決！點擊下方按鈕開啟你的私密手牌面板。"

            await interaction.response.send_message(embed=embed, view=new_game_view)
            new_game_view.message = await interaction.original_response()
            self.stop()
        else:
            view = BlackjackLobbyView(self.bot, self.host_id, channel=interaction.channel)
            view.players = [p for p in self.players if not getattr(p, 'bot', False)]
            if not view.players:
                view.players.append(interaction.user)

            embed = discord.Embed(
                title="🃏 多人 21 點遊戲大廳 (上限 4 人)",
                description="運氣與策略的完美結合！\n點擊下方按鈕加入，由房主點擊開始遊戲（不足 4 人將由 AI 機器人補齊）。",
                color=discord.Color.blue()
            )
            
            player_list_lines = []
            for i, p in enumerate(view.players):
                tag = " (房主)" if p.id == self.host_id else ""
                player_list_lines.append(f"{i+1}. {p.mention} - {p.display_name}{tag}")
            
            embed.add_field(name="目前參與玩家", value="\n".join(player_list_lines), inline=False)
            embed.add_field(name="遊戲規則", value="A可算1/11，JQK算10。抽牌上限5張，滿5張不爆視為五小龍！", inline=False)

            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
            self.stop()


# ==================== 1. 遊戲大廳介面 (Lobby View) ====================
class BlackjackLobbyView(discord.ui.View):
    def __init__(self, bot, host_id, channel=None):
        super().__init__(timeout=180)
        self.bot = bot
        self.host_id = host_id
        self.channel = channel
        self.players = []
        self.message = None

    @discord.ui.button(label="參與遊戲", style=discord.ButtonStyle.success, emoji="✅", custom_id="join_game_combined")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            if len(self.players) >= 4:
                await interaction.response.send_message("❌ 遊戲大廳已滿（最多 4 人）！", ephemeral=True)
                return

            self.players.append(interaction.user)
            
            player_list_lines = []
            for i, p in enumerate(self.players):
                tag = " (房主)" if p.id == self.host_id else ""
                player_list_lines.append(f"{i+1}. {p.mention} - {p.display_name}{tag}")

            embed = interaction.message.embeds[0]
            embed.fields[0].value = "\n".join(player_list_lines)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("你已經在遊戲大廳囉！", ephemeral=True)

    @discord.ui.button(label="開始遊戲", style=discord.ButtonStyle.primary, emoji="🟧", custom_id="start_game_combined")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("只有開房者才能開始遊戲！", ephemeral=True)
            return
        if not self.players:
            await interaction.response.send_message("目前沒有任何玩家，無法開始！", ephemeral=True)
            return
        
        # 💡 新增：不足 4 人時，由 AI 機器人自動補齊至 4 人！
        bot_pool = ["賭神小艾", "牌局小助手", "牌桌路人甲", "摸魚高手"]
        while len(self.players) < 4:
            used_names = [p.display_name for p in self.players]
            available_names = [n for n in bot_pool if n not in used_names]
            if not available_names:
                available_names = [f"AI機器人{len(self.players)+1}"]
            self.players.append(AIBotPlayer(available_names[0]))

        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        
        game_view = BlackjackGameView(self.bot, self.players, self.host_id, is_solo=False, channel=interaction.channel)
        await game_view.process_ai_turns_if_needed()

        msg = await interaction.channel.send(embed=game_view.create_embed(), view=game_view)
        game_view.message = msg
        self.stop()


# ==================== Cog 主體結構 ====================
class BlackjackCombined(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ 缺少必要的參數！請檢查你的指令格式。", delete_after=10)
        elif isinstance(error, commands.NotOwner):
            await ctx.send(f"❌ 權限不足：此指令僅限機器人擁有者使用。", delete_after=10)
        else:
            await ctx.send(f"❌ 發生未預期的錯誤：\n```py\n{error}\n```", delete_after=10)

    # 1. 傳統文字指令：維持單人模式（不變）
    @commands.command(name="blackjack", aliases=["21點"])
    async def blackjack_prefix(self, ctx):
        players = [ctx.author, AIBotPlayer("賭神小艾"), AIBotPlayer("牌局小助手")]
        game_view = BlackjackGameView(self.bot, players, ctx.author.id, is_solo=True, channel=ctx.channel)
        await game_view.process_ai_turns_if_needed()

        embed = game_view.create_embed()
        embed.title = "🃏 單人盲牌對戰模式"
        embed.description = "與 2 位 AI 玩家及 AI 莊家展開 21 點盲牌對決！點擊下方按鈕開啟你的私密手牌面板。"

        msg = await ctx.send(embed=embed, view=game_view)
        game_view.message = msg

    # 2. 斜線指令：多人大廳模式（上限 4 人，不足自動補 AI）
    @app_commands.command(name="21點", description="開啟一個多人 21 點盲牌遊戲大廳 (最多 4 人)")
    async def blackjack_slash(self, interaction: discord.Interaction):
        view = BlackjackLobbyView(self.bot, interaction.user.id, channel=interaction.channel)
        view.players.append(interaction.user)

        embed = discord.Embed(
            title="🃏 多人 21 點遊戲大廳 (上限 4 人)",
            description="運氣與策略的完美結合！\n點擊下方按鈕加入，由房主點擊開始遊戲（不足 4 人將由 AI 機器人補齊）。",
            color=discord.Color.blue()
        )
        player_list = f"1. {interaction.user.mention} - {interaction.user.display_name} (房主)"
        embed.add_field(name="目前參與玩家", value=player_list, inline=False)
        embed.add_field(name="遊戲規則", value="A可算1/11，JQK算10。抽牌上限5張，滿5張不爆視為五小龍！", inline=False)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(BlackjackCombined(bot))