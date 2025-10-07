import json
from types import SimpleNamespace

import pytest
from django.urls import reverse

from cookbook.helper.ai_prompts import DEFAULT_IMPORT_PROMPT_TEXT, combine_import_prompts
from cookbook.models import AiProvider
from cookbook.serializer import AiImportSerializer


@pytest.mark.parametrize(
    "data,expected_prompt",
    [
        ({'ai_provider_id': 1, 'text': 'data'}, None),
        ({'ai_provider_id': 1, 'text': 'data', 'prompt': 'custom'}, 'custom'),
    ],
)
def test_ai_import_serializer_prompt_optional(data, expected_prompt):
    serializer = AiImportSerializer(data=data, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data.get('prompt') == expected_prompt


@pytest.mark.django_db()
def test_ai_import_prompt_merges_customizations(monkeypatch, u1_s1, space_1):
    ai_provider = AiProvider.objects.create(
        name='Test Provider',
        api_key='test-key',
        model_name='test-model',
        space=space_1,
        import_prompt='Provider guidance',
    )

    observed = {}

    def fake_completion(**kwargs):
        observed['messages'] = kwargs['messages']
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "@context": "https://schema.org",
                                "@type": "Recipe",
                                "name": "AI Recipe",
                                "recipeIngredient": [],
                                "recipeInstructions": [],
                            }
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr('cookbook.views.api.completion', fake_completion)
    monkeypatch.setattr('cookbook.views.api.helper.get_from_scraper', lambda *args, **kwargs: {
        'name': 'AI Recipe',
        'keywords': [],
        'steps': [],
        'servings': None,
        'servings_text': '',
        'working_time': None,
        'waiting_time': None,
        'source_url': '',
    })
    monkeypatch.setattr('cookbook.views.api.get_images_from_soup', lambda *args, **kwargs: [])
    monkeypatch.setattr('cookbook.views.api.scrape_html', lambda *args, **kwargs: SimpleNamespace(schema=SimpleNamespace(data={}), soup=None))

    response = u1_s1.post(
        reverse('api_ai_import'),
        {
            'ai_provider_id': ai_provider.id,
            'text': 'Recipe text',
            'prompt': 'User override',
            'file': '',
            'recipe_id': '',
        },
    )

    assert response.status_code == 200
    expected_prompt = combine_import_prompts(
        DEFAULT_IMPORT_PROMPT_TEXT,
        ai_provider.import_prompt,
        'User override',
    )
    assert observed['messages'][0]['content'][0]['text'] == expected_prompt
