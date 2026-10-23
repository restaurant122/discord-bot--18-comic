import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio

COLORS = ['紅色', '黃色', '綠色', '藍色']
COLOR_EMOJIS = {'紅色': '🟥', '黃色': '🟨', '綠色': '🟩', '藍色': '🟦'}
WILD_COLORS = ['紅色', '黃色', '綠色', '藍色']

# 用來追蹤目前有哪些頻道正在進行 UNO 遊戲或大廳
active_uno_channels = set()

# ==================== 自動刪除訊息小幫手 ====================
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


# ==================== 4. 私密手牌與操作面板 (Ephemeral View) ====================
class UnoPlaySelect(discord.ui.Select):
    def __init__(self, playable_cards, game_view):
        options = []
        for idx, card in playable_cards:
            emoji = COLOR_EMOJIS.get(card['color'], '🌈')
            label = f"{card['color']} {card['value']}" if card['color'] != '黑色' else f"{card['value']}"
            options.append(discord.SelectOption(label=label, value=str(idx), emoji=emoji))

        super().__init__(placeholder="請選擇你要出的牌...", min_values=1, max_values=1, options=options)
        self.game_view = game_view

    async def callback(self, interaction: discord.Interaction):
        card_idx = int(self.values[0])
        game_view = self.game_view
        
        selected_card = game_view.hands[interaction.user.id][card_idx]
        if selected_card['color'] == '黑色':
            hand = game_view.hands[interaction.user.id]
            hand_strs = [f"{COLOR_EMOJIS.get(c['color'], '🌈')} `{c['color'] if c['color'] != '黑色' else ''} {c['value']}`" for c in hand]
            hand_display = "\n".join(hand_strs) if hand_strs else "（無剩餘手牌）"

            color_view = UnoColorChoiceView(game_view, interaction.user.id, card_idx)
            await interaction.response.edit_message(
                content=f"🔐 **【目前手牌】** (剩餘 {len(hand)} 張牌)\n{hand_display}\n\n🌈 請選擇你要變更的顏色：",
                view=color_view
            )
        else:
            game_view.cancel_turn_timer()
            is_win, msg, result = game_view.apply_play_card(interaction.user.id, card_idx)
            await interaction.response.edit_message(content=f"{msg}\n\n*(此訊息 3 秒後自動刪除)*", view=None)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))
            
            if is_win:
                await game_view.finalize_game()
            else:
                skip, draw_penalty = result
                await game_view.next_temp_turn(skip=skip, draw_penalty=draw_penalty)
                await game_view.update_public_message()


class UnoColorChoiceView(discord.ui.View):
    def __init__(self, game_view, player_id, card_idx):
        super().__init__(timeout=180)
        self.game_view = game_view
        self.player_id = player_id
        self.card_idx = card_idx

    @discord.ui.button(label="紅色", style=discord.ButtonStyle.danger, emoji="🟥")
    async def red_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_color_choice(interaction, '紅色')

    @discord.ui.button(label="黃色", style=discord.ButtonStyle.secondary, emoji="🟨")
    async def yellow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_color_choice(interaction, '黃色')

    @discord.ui.button(label="綠色", style=discord.ButtonStyle.success, emoji="🟩")
    async def green_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_color_choice(interaction, '綠色')

    @discord.ui.button(label="藍色", style=discord.ButtonStyle.primary, emoji="🟦")
    async def blue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_color_choice(interaction, '藍色')

    async def handle_color_choice(self, interaction: discord.Interaction, chosen_color: str):
        self.game_view.cancel_turn_timer()
        is_win, msg, result = self.game_view.apply_play_card(self.player_id, self.card_idx, chosen_color=chosen_color)
        await interaction.response.edit_message(content=f"{msg}\n\n*(此訊息 3 秒後自動刪除)*", view=None)
        asyncio.create_task(delete_interaction_after_delay(interaction, 3))
        
        if is_win:
            await self.game_view.finalize_game()
        else:
            skip, draw_penalty = result
            await self.game_view.next_temp_turn(skip=skip, draw_penalty=draw_penalty)
            await self.game_view.update_public_message()


class PlayerControlView(discord.ui.View):
    def __init__(self, game_view, player_id):
        super().__init__(timeout=180)
        self.game_view = game_view
        self.player_id = player_id

        is_my_turn = (not game_view.game_over and game_view.players[game_view.current_player_index].id == player_id)

        if is_my_turn:
            hand = game_view.hands.get(player_id, [])
            top_card = game_view.discard_pile[-1]
            current_color = game_view.current_color

            playable = []
            for idx, card in enumerate(hand):
                if game_view.is_card_playable(card, top_card, current_color):
                    playable.append((idx, card))

            if playable:
                self.add_item(UnoPlaySelect(playable, game_view))

    @discord.ui.button(label="抽一張牌 (Draw)", style=discord.ButtonStyle.secondary, emoji="📥")
    async def draw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        game_view = self.game_view
        drawn_card = game_view.draw_card()
        game_view.hands[self.player_id].append(drawn_card)

        top_card = game_view.discard_pile[-1]
        curr_color = game_view.current_color
        card_str = f"{drawn_card['value']}" if drawn_card['color'] == '黑色' else f"{drawn_card['color']} {drawn_card['value']}"

        if game_view.is_card_playable(drawn_card, top_card, curr_color):
            card_idx = len(game_view.hands[self.player_id]) - 1
            if drawn_card['color'] == '黑色':
                hand = game_view.hands[self.player_id]
                hand_strs = [f"{COLOR_EMOJIS.get(c['color'], '🌈')} `{c['color'] if c['color'] != '黑色' else ''} {c['value']}`" for c in hand]
                hand_display = "\n".join(hand_strs) if hand_strs else "（無剩餘手牌）"

                color_view = UnoColorChoiceView(game_view, self.player_id, card_idx)
                await interaction.response.edit_message(
                    content=f"📥 你抽到了 `{card_str}`！這張牌可以打出。\n🔐 **【目前手牌】** (剩餘 {len(hand)} 張牌)\n{hand_display}\n\n🌈 請選擇你要變更的顏色：",
                    view=color_view
                )
            else:
                is_win, msg, result = game_view.apply_play_card(self.player_id, card_idx)
                await interaction.response.edit_message(content=f"📥 你抽到了 `{card_str}`，並直接打出！\n{msg}\n\n*(此訊息 3 秒後自動刪除)*", view=None)
                asyncio.create_task(delete_interaction_after_delay(interaction, 3))

                if is_win:
                    await game_view.finalize_game()
                else:
                    skip, draw_penalty = result
                    await game_view.next_temp_turn(skip=skip, draw_penalty=draw_penalty)
                    await game_view.update_public_message()
        else:
            await interaction.response.edit_message(content=f"📥 你抽到了 `{card_str}`（無法打出），回合結束。\n\n*(此訊息 3 秒後自動刪除)*", view=None)
            asyncio.create_task(delete_interaction_after_delay(interaction, 3))

            await game_view.next_temp_turn()
            await game_view.update_public_message()


# ==================== 3. 遊戲進行中的公開介面與結算視圖 ====================
class GameOverView(discord.ui.View):
    def __init__(self, game_view):
        super().__init__(timeout=180)
        self.game_view = game_view

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

        view = UnoLobbyView(self.game_view.bot, self.game_view.host_id, channel=interaction.channel)
        view.players = [p for p in self.game_view.players if not getattr(p, 'bot', False)]
        if not view.players:
            view.players.append(interaction.user)

        lobby_embed = discord.Embed(
            title="🎴 多人 UNO 遊戲大廳 (上限 5 人)",
            description="點擊下方按鈕加入，由房主點擊開始遊戲（不足 5 人將由 AI 機器人自動補齊）。",
            color=discord.Color.blue()
        )
        
        player_list_lines = []
        for i, p in enumerate(view.players):
            tag = " (房主)" if p.id == self.game_view.host_id else ""
            p_name = getattr(p, 'display_name', getattr(p, 'name', '玩家'))
            player_list_lines.append(f"{i+1}. {p.mention} - {p_name}{tag}")
        
        lobby_embed.add_field(name="目前參與玩家", value="\n".join(player_list_lines), inline=False)
        lobby_embed.add_field(name="遊戲規則", value="每人起始 7 張牌，同色或同數字可出牌。萬用牌可變色，+2/+4會強制對手抽牌！", inline=False)

        msg = await interaction.channel.send(embed=lobby_embed, view=view)
        view.message = msg
        active_uno_channels.add(interaction.channel.id)
        self.stop()

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
        active_uno_channels.discard(interaction.channel.id)
        self.stop()


class UnoGameView(discord.ui.View):
    def __init__(self, bot, players, host_id, is_solo=False, channel=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.players = players
        self.host_id = host_id
        self.is_solo = is_solo
        self.channel = channel
        
        self.hands = {p.id: [] for p in players}
        self.deck = []
        self.discard_pile = []
        self.current_player_index = 0
        self.direction = 1
        self.current_color = ""
        self.game_over = False
        self.winner = None
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

    def initialize_deck(self):
        self.deck = []
        for color in COLORS:
            self.deck.append({'color': color, 'value': '0'})
            for val in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '禁止', '反轉', '+2']:
                self.deck.append({'color': color, 'value': val})
                self.deck.append({'color': color, 'value': val})

        for _ in range(4):
            self.deck.append({'color': '黑色', 'value': '變色'})
            self.deck.append({'color': '黑色', 'value': '+4'})

        random.shuffle(self.deck)

    def draw_card(self):
        if not self.deck:
            top = self.discard_pile.pop()
            self.deck = self.discard_pile[:]
            self.discard_pile = [top]
            random.shuffle(self.deck)
        return self.deck.pop()

    def deal_initial_cards(self):
        for _ in range(7):
            for p in self.players:
                self.hands[p.id].append(self.draw_card())

        while True:
            first_card = self.draw_card()
            if first_card['color'] != '黑色':
                self.discard_pile.append(first_card)
                self.current_color = first_card['color']
                break
            else:
                self.deck.insert(0, first_card)

    def is_card_playable(self, card, top_card, current_color):
        if card['color'] == '黑色':
            return True
        if card['color'] == current_color:
            return True
        if card['value'] == top_card['value']:
            return True
        return False

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

        hand = self.hands[interaction.user.id]
        hand_strs = [f"{COLOR_EMOJIS.get(c['color'], '🌈')} `{c['color'] if c['color'] != '黑色' else ''} {c['value']}`" for c in hand]
        hand_display = "\n".join(hand_strs) if hand_strs else "（無剩餘手牌）"

        is_my_turn = (not self.game_over and self.players[self.current_player_index].id == interaction.user.id)
        turn_status = "✨ **目前輪到你的回合！** 請使用下方按鈕進行操作：" if is_my_turn else "⏳ 目前還沒輪到你的回合，您可以先查看手牌。"

        view = PlayerControlView(self, interaction.user.id) if is_my_turn else None

        await interaction.response.send_message(
            f"🔐 **【私密手牌面板】** (剩餘 {len(hand)} 張牌)\n{hand_display}\n\n{turn_status}",
            view=view,
            ephemeral=True
        )

    def create_embed(self):
        embed = discord.Embed(title="🎴 UNO 盲牌對戰進行中", color=discord.Color.gold())
        
        top_card = self.discard_pile[-1]
        top_emoji = COLOR_EMOJIS.get(self.current_color, '🌈')
        top_display = f"{top_emoji} **{self.current_color}** (棄牌堆頂端: `{top_card['color']} {top_card['value']}`)"
        
        embed.add_field(name="📌 目前檯面顏色與卡牌", value=top_display, inline=False)
        embed.add_field(name="🔄 出牌方向", value="順時針 ➡️" if self.direction == 1 else "⬅️ 逆時針", inline=False)

        next_player_index = (self.current_player_index + self.direction) % len(self.players) if not self.game_over else -1

        player_status_lines = []
        for i, p in enumerate(self.players):
            count = len(self.hands[p.id])
            is_turn = (i == self.current_player_index and not self.game_over)
            is_next = (i == next_player_index and not self.game_over)
            
            pointer = ""
            if is_turn:
                pointer = "▶️ **[思考中...]** "
            elif is_next:
                pointer = "➡️ **[下一位]** "
                
            uno_tag = " 🔥 **UNO!**" if count == 1 else ""
            p_name = getattr(p, 'display_name', getattr(p, 'name', '玩家'))
            player_status_lines.append(f"{pointer}{p_name}: **{count} 張牌**{uno_tag}")

        embed.add_field(name="👥 玩家狀態", value="\n".join(player_status_lines), inline=False)

        if not self.game_over:
            current_user = self.players[self.current_player_index]
            c_name = getattr(current_user, 'display_name', getattr(current_user, 'name', '玩家'))
            embed.set_footer(text=f"目前輪到: {c_name} 操作中 (點擊按鈕開啟手牌)")
        else:
            embed.title = "🏆 UNO 對戰結算排行榜"
            embed.color = discord.Color.purple()
            
            rank_data = sorted(self.players, key=lambda p: len(self.hands[p.id]))
            leaderboard_lines = []
            for idx, p in enumerate(rank_data):
                p_name = getattr(p, 'display_name', getattr(p, 'name', '玩家'))
                cnt = len(self.hands[p.id])
                winner_tag = " 🎉 獲勝者！" if (idx == 0 and not self.timeout_player_name) else ""
                leaderboard_lines.append(f"**第 {idx + 1} 名**: {p_name} — 剩餘 **{cnt} 張牌**{winner_tag}")

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

    def apply_play_card(self, player_id, card_idx, chosen_color=None):
        hand = self.hands[player_id]
        card = hand.pop(card_idx)
        self.discard_pile.append(card)

        if card['color'] == '黑色':
            self.current_color = chosen_color
        else:
            self.current_color = card['color']

        if len(hand) == 0:
            self.game_over = True
            self.winner = player_id
            card_str = f"{card['value']}" if card['color'] == '黑色' else f"{card['color']} {card['value']}"
            if chosen_color:
                card_str += f" (變為{chosen_color})"
            return True, f"🎉 你打出了 `{card_str}` 並贏得了勝利！", True

        skip = False
        draw_penalty = 0

        if card['value'] == '禁止':
            skip = True
        elif card['value'] == '反轉':
            if len(self.players) == 2:
                skip = True
            else:
                self.direction *= -1
        elif card['value'] == '+2':
            draw_penalty = 2
            skip = True
        elif card['value'] == '+4':
            draw_penalty = 4
            skip = True

        card_str = f"{card['value']}" if card['color'] == '黑色' else f"{card['color']} {card['value']}"
        if chosen_color:
            card_str += f" (變為{chosen_color})"

        return False, f"✅ 你打出了 `{card_str}`！", (skip, draw_penalty)

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
            game_over_view = GameOverView(self)
            self.message = await self.channel.send(embed=self.create_embed(), view=game_over_view)

    async def start_turn_timer(self, player):
        """180秒回合超時倒數計時"""
        try:
            await asyncio.sleep(180)
            if not self.game_over:
                await self.finalize_game(timeout_player=player)
        except asyncio.CancelledError:
            pass

    async def process_ai_turns_if_needed(self):
        while not self.game_over and self.current_player_index < len(self.players):
            current_user = self.players[self.current_player_index]

            if getattr(current_user, 'bot', False):
                hand = self.hands[current_user.id]
                top_card = self.discard_pile[-1]
                curr_color = self.current_color

                playable_indices = [i for i, c in enumerate(hand) if self.is_card_playable(c, top_card, curr_color)]

                if playable_indices:
                    choice_idx = playable_indices[0]
                    card = hand.pop(choice_idx)
                    self.discard_pile.append(card)

                    chosen_color = None
                    if card['color'] == '黑色':
                        chosen_color = random.choice(WILD_COLORS)
                        self.current_color = chosen_color
                    else:
                        self.current_color = card['color']

                    if len(self.hands[current_user.id]) == 0:
                        self.game_over = True
                        await self.finalize_game()
                        break

                    skip = False
                    draw_penalty = 0

                    if card['value'] == '禁止':
                        skip = True
                    elif card['value'] == '反轉':
                        if len(self.players) == 2:
                            skip = True
                        else:
                            self.direction *= -1
                    elif card['value'] == '+2':
                        draw_penalty = 2
                        skip = True
                    elif card['value'] == '+4':
                        draw_penalty = 4
                        skip = True

                    await self.next_turn(skip=skip, draw_penalty=draw_penalty)
                else:
                    drawn = self.draw_card()
                    hand.append(drawn)

                    if self.is_card_playable(drawn, top_card, self.current_color):
                        card = hand.pop()
                        self.discard_pile.append(card)

                        if card['color'] == '黑色':
                            self.current_color = random.choice(WILD_COLORS)
                        else:
                            self.current_color = card['color']

                        if len(self.hands[current_user.id]) == 0:
                            self.game_over = True
                            await self.finalize_game()
                            break

                        skip = False
                        draw_penalty = 0

                        if card['value'] == '禁止':
                            skip = True
                        elif card['value'] == '反轉':
                            if len(self.players) == 2:
                                skip = True
                            else:
                                self.direction *= -1
                        elif card['value'] == '+2':
                            draw_penalty = 2
                            skip = True
                        elif card['value'] == '+4':
                            draw_penalty = 4
                            skip = True

                        await self.next_turn(skip=skip, draw_penalty=draw_penalty)
                    else:
                        await self.next_turn()
            else:
                self.cancel_turn_timer()
                self.turn_timer_task = asyncio.create_task(self.start_turn_timer(current_user))
                break

    async def next_temp_turn(self, skip=False, draw_penalty=0):
        step = self.direction * (2 if skip else 1)
        self.current_player_index = (self.current_player_index + step) % len(self.players)

        if draw_penalty > 0:
            target_player = self.players[self.current_player_index]
            for _ in range(draw_penalty):
                self.hands[target_player.id].append(self.draw_card())

        await self.process_ai_turns_if_needed()

    async def next_turn(self, skip=False, draw_penalty=0):
        await self.next_temp_turn(skip=skip, draw_penalty=draw_penalty)


# ==================== 1. 遊戲大廳介面 (Lobby View) ====================
class UnoLobbyView(discord.ui.View):
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
            active_uno_channels.discard(self.channel.id)

    @discord.ui.button(label="參與遊戲", style=discord.ButtonStyle.success, emoji="✅")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            if len(self.players) >= 5:
                await interaction.response.send_message("❌ 遊戲大廳已滿（最多 5 人）！\n*(此訊息 3 秒後自動刪除)*", ephemeral=True)
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

        bot_pool = ["賭神小艾", "牌局小助手", "牌桌路人甲", "摸魚高手", "出牌大師"]
        while len(self.players) < 5:
            used_names = [getattr(p, 'display_name', getattr(p, 'name', '')) for p in self.players]
            available_names = [n for n in bot_pool if n not in used_names]
            if not available_names:
                available_names = [f"AI機器人{len(self.players)+1}"]
            self.players.append(AIBotPlayer(available_names[0]))

        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass

        game_view = UnoGameView(self.bot, self.players, self.host_id, is_solo=False, channel=interaction.channel)
        
        msg = await interaction.channel.send(embed=game_view.create_embed(), view=game_view)
        game_view.message = msg
        
        await game_view.process_ai_turns_if_needed()
        self.stop()


# ==================== Cog 主體結構 ====================
class UnoCombined(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="uno", description="開啟一個多人 UNO 盲牌遊戲大廳 (最多 5 人)")
    async def uno_slash(self, ctx: commands.Context):
        channel_id = ctx.channel.id
        if channel_id in active_uno_channels:
            msg_text = "❌ 此頻道已經有一個進行中或等待中的 UNO 遊戲大廳了！\n*(此訊息 3 秒後自動刪除)*"
            if ctx.interaction:
                await ctx.interaction.response.send_message(msg_text, ephemeral=True)
                asyncio.create_task(delete_interaction_after_delay(ctx.interaction, 3))
            else:
                msg = await ctx.send("❌ 此頻道已經有一個進行中或等待中的 UNO 遊戲大廳了！")
                asyncio.create_task(delete_message_after_delay(msg, 3))
            return

        active_uno_channels.add(channel_id)
        author = ctx.author
        
        view = UnoLobbyView(self.bot, author.id, channel=ctx.channel)
        view.players.append(author)

        embed = discord.Embed(
            title="🎴 多人 UNO 遊戲大廳 (上限 5 人)",
            description="點擊下方按鈕加入，由房主點擊開始遊戲（不足 5 人將由 AI 機器人自動補齊）。",
            color=discord.Color.blue()
        )
        player_list = f"1. {author.mention} - {author.display_name} (房主)"
        embed.add_field(name="目前參與玩家", value=player_list, inline=False)
        embed.add_field(name="遊戲規則", value="每人起始 7 張牌，同色或同數字可出牌。萬用牌可變色，+2/+4會強制對手抽牌！", inline=False)

        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            view.message = await ctx.interaction.original_response()
        else:
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg


async def setup(bot):
    await bot.add_cog(UnoCombined(bot))