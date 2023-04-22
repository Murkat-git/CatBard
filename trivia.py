import discord
import random
from typing import List


class TriviaButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(style=discord.ButtonStyle.secondary, label=label)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: Trivia = self.view
        correct_answer = view.correct_answer
        if self.label == correct_answer:
            self.style = discord.ButtonStyle.success
        else:
            self.style = discord.ButtonStyle.danger
            for child in self.view.children:
                if child.label == correct_answer:
                    child.style = discord.ButtonStyle.success
        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(view=view, delete_after=5)


class Trivia(discord.ui.View):
    correct_answer: str
    children: List[TriviaButton]

    def __init__(self, data):
        super().__init__()
        self.correct_answer = data['correct_answer']

        answers = data['incorrect_answers'] + [data['correct_answer']]
        random.shuffle(answers)
        for i in answers:
            self.add_item(TriviaButton(i))
