from functools import partial

from discord.ui import Button, View

from psychotropic.embeds import DefaultEmbed


class Paginator(View):
    def __init__(self, make_embed, page=1, last_page=None):
        """Agnostic embed paginator using buttons to navigate between pages.

        - `make_embed` is a coroutine taking a page number as argument which
          will be called to regenerate the embed content;
        - `page` is the default page number;
        - `last_page` is the number of the last page. If `None`, the paginator
          will be endless.
        """
        super().__init__()

        self.make_embed = make_embed
        self.page = page
        self.last_page = last_page

        for offset, id_, label, emoji in (
            (-1, 'prev', "Previous", "⏮️"),
            (1,  'next', "Next",     "⏭️")
        ):
            button = Button(custom_id=id_, label=label, emoji=emoji)
            button.callback = partial(self.change_page, offset)
            self.add_item(button)

        self._update_button_status()

    def _update_button_status(self):
        for child in self.children:
            match child.custom_id:
                case 'prev':
                    child.disabled = self.page <= 1
                case 'next':
                    child.disabled = (
                        self.last_page and self.page >= self.last_page
                    )

    async def change_page(self, offset, interaction):
        page = self.page + offset

        if page < 1 or (self.last_page and page > self.last_page):
            raise ValueError(f"Out of bounds page number {page}.")

        await interaction.response.edit_message(
            embed = DefaultEmbed(
                title = "Computing...",
                description = "Relax, it will just take a year or two."
            ),
            view = None
        )

        # Making the embed can be long when fetching external data
        embed = await self.make_embed(page)
        self.page = page
        self._update_button_status()

        await interaction.followup.edit_message(
            interaction.message.id,
            embed = embed,
            view = self
        )
