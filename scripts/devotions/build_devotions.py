"""Builds the Catholic devotional reference data: the Rosary, traditional prayers, and the Baltimore
Catechism No. 2 — every text public domain, every source named in the file it writes.

    python scripts/devotions/build_devotions.py      # from the realm root; downloads into data/source/

The Rosary's mysteries and their weekday assignment are the Church's own (the Luminous Mysteries and
the Thursday assignment were added by John Paul II, Rosarium Virginis Mariae, 2002). Each mystery
names the Scripture that tells it, as a verse range in this realm's reference form and the OSIS
chapter it falls in, so a mystery joins straight to its Passage.
"""
import html, json, os, re, urllib.request
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'data', 'source', 'catechism')
REF = os.path.join(ROOT, 'reference')
UA = {'User-Agent': 'realm-bible-build/0.1 (https://github.com/embabel-worlds/realm-bible)'}
BALTIMORE = ('https://www.gutenberg.org/cache/epub/14552/pg14552.txt', 'pg14552.txt')


class Quoted(str):
    pass


yaml.add_representer(Quoted, lambda d, v: d.represent_scalar('tag:yaml.org,2002:str', v, style='"'))


def q(v):
    """Every string quoted: an unquoted date or number-looking string can be read back as another type."""
    if isinstance(v, str):
        return Quoted(v)
    if isinstance(v, list):
        return [q(x) for x in v]
    if isinstance(v, dict):
        return {k: q(x) for k, x in v.items()}
    return v


def write(name, header, records):
    with open(os.path.join(REF, name), 'w') as f:
        f.write(header.rstrip() + '\n\n')
        yaml.dump(q(records), f, allow_unicode=True, sort_keys=False, width=10_000)


# ── The Rosary ───────────────────────────────────────────────────────────────────────────────
# (set, number, name, Scripture, OSIS chapter, the fruit traditionally asked for)
MYSTERIES = [
    ('joyful', 1, 'The Annunciation', 'Luke 1:26-38', 'Luke.1', 'Humility'),
    ('joyful', 2, 'The Visitation', 'Luke 1:39-56', 'Luke.1', 'Love of neighbour'),
    ('joyful', 3, 'The Nativity', 'Luke 2:1-20', 'Luke.2', 'Poverty of spirit'),
    ('joyful', 4, 'The Presentation in the Temple', 'Luke 2:22-38', 'Luke.2', 'Obedience'),
    ('joyful', 5, 'The Finding in the Temple', 'Luke 2:41-52', 'Luke.2', 'Joy in finding Jesus'),
    ('luminous', 1, 'The Baptism of the Lord', 'Matthew 3:13-17', 'Matt.3', 'Openness to the Holy Spirit'),
    ('luminous', 2, 'The Wedding at Cana', 'John 2:1-11', 'John.2', 'To Jesus through Mary'),
    ('luminous', 3, 'The Proclamation of the Kingdom', 'Mark 1:14-15', 'Mark.1', 'Repentance and trust in God'),
    ('luminous', 4, 'The Transfiguration', 'Matthew 17:1-8', 'Matt.17', 'Desire for holiness'),
    ('luminous', 5, 'The Institution of the Eucharist', 'Matthew 26:26-28', 'Matt.26', 'Adoration'),
    ('sorrowful', 1, 'The Agony in the Garden', 'Matthew 26:36-46', 'Matt.26', 'Sorrow for sin'),
    ('sorrowful', 2, 'The Scourging at the Pillar', 'John 19:1', 'John.19', 'Purity'),
    ('sorrowful', 3, 'The Crowning with Thorns', 'Matthew 27:27-31', 'Matt.27', 'Courage'),
    ('sorrowful', 4, 'The Carrying of the Cross', 'Luke 23:26-32', 'Luke.23', 'Patience'),
    ('sorrowful', 5, 'The Crucifixion', 'Luke 23:33-46', 'Luke.23', 'Perseverance'),
    ('glorious', 1, 'The Resurrection', 'Matthew 28:1-10', 'Matt.28', 'Faith'),
    ('glorious', 2, 'The Ascension', 'Acts 1:6-11', 'Acts.1', 'Hope'),
    ('glorious', 3, 'The Descent of the Holy Spirit', 'Acts 2:1-13', 'Acts.2', 'Love of God'),
    ('glorious', 4, 'The Assumption of Mary', 'Revelation 12:1', 'Rev.12', 'Grace of a happy death'),
    ('glorious', 5, 'The Coronation of Mary', 'Revelation 12:1', 'Rev.12', "Trust in Mary's intercession"),
]
DAYS = {'Monday': 'joyful', 'Tuesday': 'sorrowful', 'Wednesday': 'glorious', 'Thursday': 'luminous',
        'Friday': 'sorrowful', 'Saturday': 'joyful', 'Sunday': 'glorious'}


def rosary():
    records = []
    for s, n, name, ref, osis, fruit in MYSTERIES:
        note = {'glorious': {4: 'Not narrated in Scripture; the Church reads Revelation 12 of it.',
                             5: 'Not narrated in Scripture; the Church reads Revelation 12 of it.'}}.get(s, {}).get(n, '')
        records.append({'type': 'RosaryMystery',
                        'data': {'key': f'{s}-{n}', 'set': s, 'number': n, 'name': name, 'scripture': ref,
                                 'osis': osis, 'fruit': fruit, 'note': note},
                        'relations': [{'predicate': 'TOLD_IN', 'to': {'type': 'Passage', 'osis': osis}}]})
    for day, s in DAYS.items():
        records.append({'type': 'RosaryDay', 'data': {'weekday': day, 'set': s}})
    write('catholic-rosary.yml', """
# The four sets of the mysteries of the Rosary, the Scripture each meditates, the fruit traditionally
# asked for, and the set prayed on each day of the week (Rosarium Virginis Mariae, 2002). Facts of the
# Church's devotional practice, not anyone's text. Generated by scripts/devotions/build_devotions.py.
""", records)
    return len(records)


# ── Traditional prayers ──────────────────────────────────────────────────────────────────────
# The traditional English forms, in use for centuries and public domain. The Rosary's own sequence
# is described, not reproduced from any one booklet.
PRAYERS = [
    ('sign-of-the-cross', 'The Sign of the Cross', 'In the name of the Father, and of the Son, and of the Holy Spirit. Amen.'),
    ('our-father', 'Our Father', 'Our Father, who art in heaven, hallowed be thy name; thy kingdom come; thy will be done on earth as it is in heaven. Give us this day our daily bread; and forgive us our trespasses, as we forgive those who trespass against us; and lead us not into temptation, but deliver us from evil. Amen.'),
    ('hail-mary', 'Hail Mary', 'Hail Mary, full of grace, the Lord is with thee; blessed art thou among women, and blessed is the fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our death. Amen.'),
    ('glory-be', 'Glory Be', 'Glory be to the Father, and to the Son, and to the Holy Spirit; as it was in the beginning, is now, and ever shall be, world without end. Amen.'),
    ('fatima-prayer', 'The Fatima Prayer', 'O my Jesus, forgive us our sins, save us from the fires of hell; lead all souls to heaven, especially those most in need of thy mercy.'),
    ('hail-holy-queen', 'Hail, Holy Queen', 'Hail, holy Queen, Mother of mercy, our life, our sweetness and our hope. To thee do we cry, poor banished children of Eve; to thee do we send up our sighs, mourning and weeping in this valley of tears. Turn then, most gracious advocate, thine eyes of mercy toward us; and after this our exile show unto us the blessed fruit of thy womb, Jesus. O clement, O loving, O sweet Virgin Mary. Pray for us, O holy Mother of God, that we may be made worthy of the promises of Christ.'),
    ('apostles-creed', "The Apostles' Creed", 'I believe in God, the Father almighty, Creator of heaven and earth; and in Jesus Christ, his only Son, our Lord; who was conceived by the Holy Spirit, born of the Virgin Mary, suffered under Pontius Pilate, was crucified, died, and was buried. He descended into hell; the third day he rose again from the dead; he ascended into heaven, and sits at the right hand of God the Father almighty; from thence he shall come to judge the living and the dead. I believe in the Holy Spirit, the holy catholic Church, the communion of saints, the forgiveness of sins, the resurrection of the body, and life everlasting. Amen.'),
    ('angelus', 'The Angelus', 'V. The Angel of the Lord declared unto Mary. R. And she conceived of the Holy Spirit. Hail Mary… V. Behold the handmaid of the Lord. R. Be it done unto me according to thy word. Hail Mary… V. And the Word was made flesh. R. And dwelt among us. Hail Mary… V. Pray for us, O holy Mother of God. R. That we may be made worthy of the promises of Christ. Let us pray: Pour forth, we beseech thee, O Lord, thy grace into our hearts; that we, to whom the Incarnation of Christ thy Son was made known by the message of an angel, may by his Passion and Cross be brought to the glory of his Resurrection. Through the same Christ our Lord. Amen.'),
    ('memorare', 'The Memorare', 'Remember, O most gracious Virgin Mary, that never was it known that anyone who fled to thy protection, implored thy help, or sought thy intercession was left unaided. Inspired by this confidence, I fly unto thee, O Virgin of virgins, my Mother; to thee do I come, before thee I stand, sinful and sorrowful. O Mother of the Word Incarnate, despise not my petitions, but in thy mercy hear and answer me. Amen.'),
    ('guardian-angel', 'Prayer to the Guardian Angel', 'Angel of God, my guardian dear, to whom God’s love commits me here, ever this day be at my side, to light and guard, to rule and guide. Amen.'),
    ('act-of-contrition', 'Act of Contrition', 'O my God, I am heartily sorry for having offended thee, and I detest all my sins because I dread the loss of heaven and the pains of hell; but most of all because they offend thee, my God, who art all good and deserving of all my love. I firmly resolve, with the help of thy grace, to confess my sins, to do penance, and to amend my life. Amen.'),
    ('st-michael', 'Prayer to Saint Michael', 'Saint Michael the Archangel, defend us in battle; be our protection against the wickedness and snares of the devil. May God rebuke him, we humbly pray; and do thou, O prince of the heavenly host, by the power of God, thrust into hell Satan and all the evil spirits who prowl about the world seeking the ruin of souls. Amen.'),
]


def prayers():
    write('catholic-prayers.yml', """
# Traditional Catholic prayers in their long-established English forms, public domain. Generated by
# scripts/devotions/build_devotions.py.
""", [{'type': 'Prayer', 'data': {'key': k, 'name': n, 'text': t}} for k, n, t in PRAYERS])
    return len(PRAYERS)


# ── Baltimore Catechism No. 2 ────────────────────────────────────────────────────────────────
def fetch(url, name):
    path = os.path.join(SRC, name)
    if not os.path.exists(path):
        os.makedirs(SRC, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r, open(path, 'wb') as f:
            f.write(r.read())
    return open(path, encoding='utf-8').read()


def baltimore():
    text = fetch(*BALTIMORE)
    body = text.split('*** START OF', 1)[1].split('*** END OF', 1)[0]
    # The lessons end where the book's appendix of prayers, Mass prayers and hymns begins; that
    # appendix comes from later printings, so it is not carried.
    lessons_end = body.index('\nMORNING PRAYERS', body.index('LESSON THIRTY-SEVENTH'))
    lessons = re.split(r'\n(LESSON [A-Z\-]+)\n', body[:lessons_end])
    records, lesson_no = [], 0
    for i in range(1, len(lessons), 2):
        lesson_no += 1
        chunk = lessons[i + 1]
        title = chunk.strip().split('\n', 1)[0].strip().title()
        for m in re.finditer(r'(\d+)\.\s*Q\.\s*(.*?)\nA\.\s*(.*?)(?=\n\s*\n\d+\.\s*Q\.|\n\s*\nLESSON|\Z)', chunk, re.S):
            number, question, answer = int(m.group(1)), ' '.join(m.group(2).split()), ' '.join(m.group(3).split())
            note = ''
            # The source is a later printing that updated answers to then-current discipline and marks
            # each change in brackets. The 1885 wording is not in it, so a revised answer is withheld
            # rather than passed off as the 1885 text.
            if '[This answer has been changed' in answer:
                answer, note = '', 'Answer revised in a later printing (current discipline); the 1885 wording is not in the source, so it is omitted.'
            answer = re.sub(r'\s*\[[^\]]*\]\s*$', '', answer)
            records.append({'type': 'CatechismEntry', 'data': {
                'key': f'baltimore-2/{number}', 'catechism': 'Baltimore Catechism No. 2', 'catechismId': 'baltimore-2',
                'part': f'Lesson {lesson_no}', 'partNumber': lesson_no, 'section': title, 'number': number,
                'question': question, 'text': answer, 'note': note}})
    write('catholic-catechism-baltimore.yml', """
# A Catechism of Christian Doctrine, No. 2 ("the Baltimore Catechism"), prepared and enjoined by order
# of the Third Plenary Council of Baltimore; imprimatur 1885. Public domain. Text from Project Gutenberg
# eBook #14552 (https://www.gutenberg.org/ebooks/14552). Generated by scripts/devotions/build_devotions.py.
""", records)
    return len(records), lesson_no


if __name__ == '__main__':
    print('rosary records', rosary())
    print('prayers', prayers())
    print('baltimore Q&As, lessons', baltimore())


# ── The Catechism of the Catholic Church: topics -> paragraph numbers -> the official text ──────
# NO text of the CCC is carried — it is under copyright. ccc-topics.json is a hand-curated map from a
# topic (or a Rosary mystery) to paragraph numbers, which are facts; each range links to the page of
# the Holy See's online edition that holds its first paragraph (crawl_ccc.py finds which page that is).
def ccc():
    pages = json.load(open(os.path.join(ROOT, 'data', 'source', 'ccc', 'paragraph-pages.json')))

    def page_of(n):
        for k in range(n, 0, -1):
            if str(k) in pages:
                return pages[str(k)]
        raise KeyError(n)

    topics = json.load(open(os.path.join(os.path.dirname(__file__), 'ccc-topics.json')))
    records = []
    for t in topics:
        refs = ', '.join(f'{a}' if a == b else f'{a}–{b}' for a, b in t['ranges'])
        links = [page_of(a) for a, _ in t['ranges']]
        key = re.sub(r'[^a-z0-9]+', '-', t['topic'].lower()).strip('-')
        rec = {'type': 'CccTopic', 'data': {
            'key': key, 'topic': t['topic'], 'paragraphs': refs, 'firstParagraph': t['ranges'][0][0],
            'url': links[0]['page'], 'section': html.unescape(links[0]['title']),
            'urls': list(dict.fromkeys(l['page'] for l in links)), 'mystery': t.get('mystery', '')}}
        if t.get('mystery'):
            rec['relations'] = [{'predicate': 'EXPLAINS', 'to': {'type': 'RosaryMystery', 'key': t['mystery']}}]
        records.append(rec)
    write('catholic-ccc-topics.yml', """
# Topics, feasts and devotions mapped to paragraph numbers of the Catechism of the Catholic Church, with
# links to the official text the Holy See publishes (https://www.vatican.va/archive/ENG0015/). Paragraph
# numbers only — the CCC's text is copyright and is not reproduced here. Curated by hand in
# scripts/devotions/ccc-topics.json; generated by scripts/devotions/build_devotions.py.
""", records)
    return records


if __name__ == '__main__' and os.environ.get('CCC', '1') == '1':
    for r in ccc():
        d = r['data']
        print(f"{d['paragraphs']:22} {d['topic'][:44]:44} -> {d['section'][:60]}")
