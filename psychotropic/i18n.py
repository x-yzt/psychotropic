import logging
from contextvars import ContextVar
from typing import Optional

from babel.support import Translations
from discord import Interaction, Locale
from discord.app_commands import TranslationContext, Translator, locale_str

from psychotropic import settings


log = logging.getLogger(__name__)


class BabelTranslator(Translator):
    def __init__(self):
        super().__init__()

        self.translations: dict[str, Translations] = {}

        for locale in settings.TRANSLATIONS:
            self.translations[locale] = Translations.load(
                settings.BASE_DIR / 'locales',
                [locale]
            )
            log.info(f"Loaded translation catalog for locale: {locale}")

    async def translate(
        self,
        string: locale_str,
        locale: Locale,
        context: TranslationContext
    ) -> Optional[str]:
        return self.get_translation(string.message, str(locale))

    def get_translation(
        self,
        string: str,
        locale: str
    ) -> Optional[str]:
        """"Synchronous method to get translations outside of
        discord.py's async translation system."""
        catalog = self.translations.get(locale)

        if catalog is None:
            return

        return catalog.gettext(string)


translator = BabelTranslator()


current_locale = ContextVar('locale', default='en-US')


def set_locale(obj: Interaction | str):
    """Helper function to set the current locale to either a locale
    string or to extract it from an Interaction object."""
    if isinstance(obj, Interaction):
        current_locale.set(str(obj.locale))
    else:
        current_locale.set(obj)


def localize(string: str) -> str:
    """Helper function to translate bare strings according to current
    context locale."""
    return translator.get_translation(string, current_locale.get()) or string


def localize_fmt(string: str, /, **kwargs) -> str:
    """Helper function to translate and format bare strings according
    to current context locale."""
    return localize(string).format(**kwargs)
