import httpx
import pytest
from test_api import FixtureIndex, FixtureModel

from orchid.app import create_app
from orchid.config import Settings


@pytest.mark.parametrize('value', ['/', 'orchid', '/a/', '//a', '/a/../b', '/a?x', '/a#x', '/a%2fb', '/a\\b'])
def test_root_path_rejects_ambiguous_paths(value):
    with pytest.raises(ValueError, match='ORCHID_ROOT_PATH'):
        Settings(root_path=value)


@pytest.mark.asyncio
async def test_prefix_static_redirect_and_api(tmp_path):
    app = create_app(Settings(root=tmp_path, root_path='/orchid-poster'), FixtureIndex(), FixtureModel('fixture'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, root_path='/orchid-poster'), base_url='https://orchid.test/orchid-poster/') as client:
        response = await client.get('/tour-preview', follow_redirects=False)
        assert response.headers['location'] == 'https://orchid.test/orchid-poster/tour-preview/'
        assert (await client.get('/api/health')).status_code == 200
        assert (await client.get('/urls.js')).status_code == 200
        asset = tmp_path / '.orchid/assets/fixture.txt'
        asset.write_text('fixture', encoding='utf-8')
        assert (await client.get('/assets/fixture.txt')).text == 'fixture'
