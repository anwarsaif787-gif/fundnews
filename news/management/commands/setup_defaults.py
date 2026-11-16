from django.core.management.base import BaseCommand
from news.models import Category, Firm, Market, Source

TOPICS = {
    'Fundraising': 'final close, first close, raises, raised, hard cap, targets, fund launch, closes, secures, debut fund',
    'Deals': 'acquire, acquires, acquisition, buyout, stake, takeover, to buy, sale of, agrees to sell',
    'People': 'appoints, appointed, joins, hires, named ceo, promoted, to lead, steps down, new cio',
    'LPs': 'pension, calpers, calstrs, sovereign wealth, endowment, commits, commitment, allocates, allocation, limited partner',
    'Regulation': 'sec, regulator, fca, asic, compliance, fined, lawsuit, probe, proposes rules, treasury',
    'Service providers': 'law firm, adds partner, hires partner, fund administrator, kirkland, freshfields, sidley, simpson thacher, latham, weil',
}

MARKETS = [
    ('Private equity', 'private equity, buyout, buyouts, pe firm, growth equity'),
    ('Venture capital', 'venture, venture capital, vc, seed, series a, startup, startups'),
    ('Private credit', 'private credit, direct lending, private debt, credit fund, senior debt'),
    ('Real estate', 'real estate, property, logistics, office, housing, rental, build-to-rent'),
    ('Infrastructure', 'infrastructure, data center, data centre, energy transition, renewable, wind, solar, geothermal, power'),
    ('Secondaries', 'secondaries, secondary, gp-led, continuation fund, gp stakes'),
    ('Hedge funds', 'hedge fund, hedge funds, long/short'),
]

FIRMS = [
    ('Blackstone', ''), ('KKR', ''), ('Carlyle Group', 'Carlyle'), ('Apollo Global Management', 'Apollo'),
    ('Brookfield', ''), ('EQT', ''), ('CVC Capital Partners', 'CVC'), ('Advent International', 'Advent'),
    ('TPG', ''), ('Bain Capital', ''), ('Ares Management', 'Ares'), ('Blue Owl', ''),
    ('Hamilton Lane', ''), ('StepStone', ''), ('Partners Group', ''), ('Macquarie', 'Macquarie Asset Management'),
    ('ICG', 'Intermediate Capital Group'), ('Warburg Pincus', ''), ('General Atlantic', ''),
    ('Ardian', ''), ('Sixth Street', ''), ('Goldman Sachs', ''), ('Pantheon', ''), ('Coller Capital', 'Coller'),
    ('Thoma Bravo', ''), ('Vista Equity Partners', 'Vista Equity'), ('Hg', 'Hgcapital'), ('Permira', ''),
    ('Bridgepoint', ''), ('Cinven', ''), ('Calpers', 'CalPERS'), ('Mubadala', 'Mubadala Capital'),
]

QUERIES = [
    ('private equity fund close', 'Fund closes'), ('private credit fund', 'Private credit'),
    ('venture capital fund raises', 'Venture funds'), ('real estate fund raises', 'Real estate funds'),
    ('infrastructure fund close', 'Infrastructure funds'), ('secondaries fund close', 'Secondaries'),
    ('hedge fund launch', 'Hedge funds'), ('private equity acquires', 'Private equity deals'),
    ('pension fund commits private equity', 'Pension commitments'),
    ('private funds SEC regulation', 'Regulation'), ('private equity appoints partner', 'People moves'),
]


class Command(BaseCommand):
    help = "Create default topics, markets, firms and news feeds (safe to run again)"

    def handle(self, *args, **kwargs):
        for name, kw in TOPICS.items():
            c, _ = Category.objects.get_or_create(name=name)
            if not c.keywords:
                c.keywords = kw
                c.save()
        for i, (name, kw) in enumerate(MARKETS):
            m, _ = Market.objects.get_or_create(name=name, defaults={'keywords': kw, 'order': i})
            if not m.keywords:
                m.keywords = kw
                m.save()
        for name, aliases in FIRMS:
            Firm.objects.get_or_create(name=name, defaults={'aliases': aliases})
        for q, label in QUERIES:
            url = 'https://news.google.com/rss/search?q=' + q.replace(' ', '+')
            Source.objects.get_or_create(feed_url=url, defaults={'name': f'Google News - {label}'})
        self.stdout.write("Defaults ready: %d topics, %d markets, %d firms, %d feeds." % (
            Category.objects.count(), Market.objects.count(), Firm.objects.count(), Source.objects.count()))
