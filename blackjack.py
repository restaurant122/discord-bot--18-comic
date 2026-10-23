import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio

# 用來追蹤目前有哪些頻道正在進行 21 點遊戲或大廳
active_blackjack_channels = set()

# ==================== 提示訊息 3 秒自動刪除小幫手 ====================
async def delete_interaction_after_delay(interaction: discord.Interaction, delay=3):
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass

async def delete_message_after_delay(msg: discord.Message, delay=3):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


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

    async def on_timeout(self):
        self.clear_items()

    @discord.ui.button(label="要牌 (Hit)", style=discord.ButtonStyle.success, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ 這不是你的操作面板！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return
        
        if self.game_view.game_over:
            await interaction.response.send_message("❌ 遊戲已經結束囉！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        current_user = self.game_view.players[self.game_view.current_player_index]
        if interaction.user.id != current_user.id:
            await interaction.response.send_message("❌ 目前還沒輪到你的回合！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        self.game_view.cancel_turn_timer()
        current_hand = self.game_view.hands[current_user.id]

        if len(current_hand) >= 5:
            await interaction.response.edit_message(
                content=f"⚠️ 抽牌上限為 **5張**！已自動為您強制停牌。\n您的手牌: {self.game_view.format_hand(current_hand, hide_first=False)} (點數: {self.game_view.calculate_score(current_hand)})\n\n*(此訊息 3 秒後自動刪除)*",
                view=None
            )
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            await self.game_view.next_turn()
            await self.game_view.update_public_message()
            return

        card = self.game_view.draw_card()
        current_hand.append(card)
        score = self.game_view.calculate_score(current_hand)
        hand_len = len(current_hand)
        card_str = f"{card['suit']}{card['rank']}"

        if hand_len >= 5 and score <= 21:
            await interaction.response.edit_message(
                content=f"🎉 恭喜達成 **5張牌上限（五小龍）**！系統已自動為您停牌。\n您的手牌: {self.game_view.format_hand(current_hand, hide_first=False)} (點數: {score})\n\n*(此訊息 3 秒後自動刪除)*",
                view=None
            )
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            await self.game_view.next_turn()
        elif score > 21:
            await interaction.response.edit_message(
                content=f"💥 哎呀，爆牌了！\n您的手牌: {self.game_view.format_hand(current_hand, hide_first=False)} (點數: {score})\n\n*(此訊息 3 秒後自動刪除)*",
                view=None
            )
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            await self.game_view.next_turn()
        elif score == 21:
            await interaction.response.edit_message(
                content=f"✨ 恭喜達到 **21 點**！系統已自動為您停牌。\n您的手牌: {self.game_view.format_hand(current_hand, hide_first=False)}\n\n*(此訊息 3 秒後自動刪除)*",
                view=None
            )
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            await self.game_view.next_turn()
        else:
            hand_str = self.game_view.format_hand(current_hand, hide_first=False)
            await interaction.response.edit_message(
                content=f"🔐 **【私密手牌面板】**\n你抽到了 `{card_str}`\n你的手牌: {hand_str}\n點數總計: **{score} 點** (共 {hand_len} 張牌)\n\n✨ **目前輪到你的回合！** 請使用下方按鈕進行動作：",
                view=self
            )
            self.game_view.turn_timer_task = asyncio.create_task(self.game_view.start_turn_timer(interaction.user))

        await self.game_view.update_public_message()

    @discord.ui.button(label="停牌 (Stand)", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ 這不是你的操作面板！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        if self.game_view.game_over:
            await interaction.response.send_message("❌ 遊戲已經結束囉！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        current_user = self.game_view.players[self.game_view.current_player_index]
        if interaction.user.id != current_user.id:
            await interaction.response.send_message("❌ 目前還沒輪到你的回合！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        self.game_view.cancel_turn_timer()
        score = self.game_view.calculate_score(self.game_view.hands[current_user.id])
        
        await interaction.response.edit_message(
            content=f"🛑 你選擇停牌。最終手牌點數為: **{score} 點**\n\n*(此訊息 3 秒後自動刪除)*",
            view=None
        )
        asyncio.create_task(delete_interaction_after_delay(interaction, 3))
        
        await self.game_view.next_turn()
        await self.game_view.update_public_message()


# ==================== 遊戲結束按鈕 (GameOver View) ====================
class BlackjackGameOverView(discord.ui.View):
    def __init__(self, game_view):
        super().__init__(timeout=180)
        self.game_view = game_view

    async def on_timeout(self):
        self.clear_items()
        if self.game_view.message:
            try:
                embed = self.game_view.message.embeds[0]
                embed.set_footer(text="⏳ 結算畫面逾時，遊戲已自動關閉。")
                await self.game_view.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass
        if self.game_view.channel:
            active_blackjack_channels.discard(self.game_view.channel.id)

    @discord.ui.button(label="🔄 再來一局", style=discord.ButtonStyle.primary)
    async def play_again_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game_view.host_id:
            await interaction.response.send_message("❌ 只有房主才能重新開局！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        self.clear_items()
        embed = interaction.message.embeds[0]
        embed.set_footer(text="🔄 已重新開局，此局已結束。")
        await interaction.response.edit_message(embed=embed, view=self)

        if self.game_view.is_solo:
            players = [interaction.user, AIBotPlayer("賭神小艾"), AIBotPlayer("牌局小助手")]
            new_game_view = BlackjackGameView(self.bot, players, interaction.user.id, is_solo=True, channel=interaction.channel)
            await new_game_view.process_ai_turns_if_needed()

            embed = new_game_view.create_embed()
            embed.title = "🃏 單人盲牌對戰模式"
            embed.description = "與 2 位 AI 玩家及 AI 莊家展開 21 點盲牌對決！點擊下方按鈕開啟你的私密手牌面板。"

            msg = await interaction.channel.send(embed=embed, view=new_game_view)
            new_game_view.message = msg
            active_blackjack_channels.add(interaction.channel.id)
        else:
            view = BlackjackLobbyView(self.game_view.bot, self.game_view.host_id, channel=interaction.channel)
            view.players = [p for p in self.game_view.players if not getattr(p, 'bot', False)]
            if not view.players:
                view.players.append(interaction.user)

            lobby_embed = discord.Embed(
                title="🃏 多人 21 點遊戲大廳 (上限 4 人)",
                description="運氣與策略的完美結合！\n點擊下方按鈕加入，由房主點擊開始遊戲（不足 4 人將由 AI 機器人補齊）。",
                color=discord.Color.blue()
            )
            
            player_list_lines = []
            for i, p in enumerate(view.players):
                tag = " (房主)" if p.id == self.game_view.host_id else ""
                player_list_lines.append(f"{i+1}. {p.mention} - {p.display_name}{tag}")
            
            lobby_embed.add_field(name="目前參與玩家", value="\n".join(player_list_lines), inline=False)
            lobby_embed.add_field(name="遊戲規則", value="A可算1/11，JQK算10。抽牌上限5張，滿5張不爆視為五小龍！", inline=False)

            msg = await interaction.channel.send(embed=lobby_embed, view=view)
            view.message = msg
            active_blackjack_channels.add(interaction.channel.id)

    @discord.ui.button(label="🛑 結束遊戲", style=discord.ButtonStyle.danger)
    async def end_game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game_view.host_id:
            await interaction.response.send_message("❌ 只有房主才能結束遊戲！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        self.clear_items()
        embed = interaction.message.embeds[0]
        embed.set_footer(text="🎮 遊戲已正式結束，感謝各位玩家的參與！")
        await interaction.response.edit_message(embed=embed, view=self)
        active_blackjack_channels.discard(interaction.channel.id)
        self.stop()


# ==================== 2. 遊戲進行中的公開介面 (Game View) ====================
class BlackjackGameView(discord.ui.View):
    def __init__(self, bot, players, host_id, is_solo=False, channel=None):
        super().__init__(timeout=None)
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
        self.timeout_player_name = None
        self.turn_timer_task = None
        
        self.initialize_deck()
        self.deal_initial_cards()
        self.update_main_buttons()

    def cancel_turn_timer(self):
        if self.turn_timer_task and not self.turn_timer_task.done():
            self.turn_timer_task.cancel()
            self.turn_timer_task = None

    async def start_turn_timer(self, player):
        """180秒回合超時倒數計時"""
        try:
            await asyncio.sleep(180)
            if not self.game_over:
                await self.finalize_game(timeout_player=player)
        except asyncio.CancelledError:
            pass

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

    async def open_control_panel(self, interaction: discord.Interaction):
        player_obj = discord.utils.get(self.players, id=interaction.user.id)
        if not player_obj:
            await interaction.response.send_message("❌ 你並不是這局遊戲的參與者！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
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
            elif self.game_over:
                if is_five_cards:
                    status = " 🐉 5張牌(自動21點)!"
                elif score == 21:
                    status = " ✨ 21點!"
            
            is_turn = (i == self.current_player_index and not self.game_over)
            pointer = "▶️ **[思考中...]** " if is_turn else ""
            
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
                
                if self.timeout_player_name and p_name == self.timeout_player_name:
                    desc = "⏳ 逾時落敗"
                elif item['is_bust']:
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
            
            if self.timeout_player_name:
                embed.set_footer(text=f"⏳ 遊戲結束：{self.timeout_player_name} 超過太久未互動！")
            else:
                embed.set_footer(text="感謝遊玩！僅限房主點擊下方按鈕。")

        return embed

    async def update_public_message(self):
        if self.message and not self.game_over:
            try:
                await self.message.edit(embed=self.create_embed(), view=self)
            except discord.HTTPException:
                pass

    async def finalize_game(self, timeout_player=None):
        self.game_over = True
        self.cancel_turn_timer()
        
        if timeout_player:
            self.timeout_player_name = getattr(timeout_player, 'display_name', getattr(timeout_player, 'name', '玩家'))

        if self.message:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
        if self.channel:
            game_over_view = BlackjackGameOverView(self)
            self.message = await self.channel.send(embed=self.create_embed(), view=game_over_view)

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
                self.cancel_turn_timer()
                self.turn_timer_task = asyncio.create_task(self.start_turn_timer(current_user))
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
        pass

    async def end_game_callback(self, interaction: discord.Interaction):
        pass


# ==================== 1. 遊戲大廳介面 (Lobby View) ====================
class BlackjackLobbyView(discord.ui.View):
    def __init__(self, bot, host_id, channel=None):
        super().__init__(timeout=180)
        self.bot = bot
        self.host_id = host_id
        self.channel = channel
        self.players = []
        self.message = None

    async def on_timeout(self):
        self.clear_items()
        if self.message:
            try:
                embed = self.message.embeds[0]
                embed.set_footer(text="⏳ 遊戲大廳因長時間無互動已自動關閉。")
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass
        if self.channel:
            active_blackjack_channels.discard(self.channel.id)

    @discord.ui.button(label="參與遊戲", style=discord.ButtonStyle.success, emoji="✅")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            if len(self.players) >= 4:
                await interaction.response.send_message("❌ 遊戲大廳已滿（最多 4 人）！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
                asyncio.create_task(delete_interaction_after_delay(interaction, 3))
                return

            self.players.append(interaction.user)
            
            player_list_lines = []
            for i, p in enumerate(self.players):
                tag = " (房主)" if p.id == self.host_id else ""
                player_list_lines.append(f"{i+1}. {p.mention} - {p.display_name}{tag}")

            embed = interaction.message.embeds[0]
            embed.set_field_at(0, name="目前參與玩家", value="\n".join(player_list_lines), inline=False)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("你已經在遊戲大廳囉！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))

    @discord.ui.button(label="開始遊戲", style=discord.ButtonStyle.primary, emoji="🟧")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ 只有開房者才能開始遊戲！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return
        if not self.players:
            await interaction.response.send_message("❌ 目前沒有任何玩家，無法開始！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return
        
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

    @commands.command(name="blackjack", aliases=["21點"])
    async def blackjack_prefix(self, ctx):
        channel_id = ctx.channel.id
        if channel_id in active_blackjack_channels:
            msg = await ctx.send("❌ 此頻道已經有一個進行中或等待中的 21 點遊戲了！")
            asyncio.create_task(delete_message_after_delay(msg, 3))
            return

        active_blackjack_channels.add(channel_id)
        players = [ctx.author, AIBotPlayer("賭神小艾"), AIBotPlayer("牌局小助手")]
        game_view = BlackjackGameView(self.bot, players, ctx.author.id, is_solo=True, channel=ctx.channel)
        await game_view.process_ai_turns_if_needed()

        embed = game_view.create_embed()
        embed.title = "🃏 單人盲牌對戰模式"
        embed.description = "與 2 位 AI 玩家及 AI 莊家展開 21 點盲牌對決！點擊下方按鈕開啟你的私密手牌面板。"

        msg = await ctx.send(embed=embed, view=game_view)
        game_view.message = msg

    @app_commands.command(name="21點", description="開啟一個多人 21 點盲牌遊戲大廳 (最多 4 人)")
    async def blackjack_slash(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        if channel_id in active_blackjack_channels:
            await interaction.response.send_message("❌ 此頻道已經有一個進行中或等待中的 21 點遊戲大廳了！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            return

        active_blackjack_channels.add(channel_id)
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
