// Mock segment texts used as fallback when backend is unavailable
export const COL_TEXTS = {
  WEB: ['in the beginning god created the heavens and the earth','now the earth was formless and empty darkness was on the surface of the deep','and gods spirit was hovering over the surface of the waters','god said let there be light and there was light','god saw the light and saw that it was good and god divided the light from the darkness','god called the light day and the darkness he called night','there was evening and there was morning one day','god said let there be an expanse in the middle of the waters'],
  ASV: ['in the beginning god created the heavens and the earth','and the earth was waste and void and darkness was upon the face of the deep','and the spirit of god moved upon the face of the waters','and god said let there be light and there was light','and god saw the light that it was good and god divided the light from the darkness','and god called the light day and the darkness he called night','and there was evening and there was morning one day','and god said let there be a firmament in the midst of the waters'],
  KJV: ['in the beginning god created the heaven and the earth','and the earth was without form and void and darkness was upon the face of the deep','and the spirit of god moved upon the face of the waters','and god said let there be light and there was light','and god saw the light that it was good and god divided the light from the darkness','and god called the light day and the darkness he called night','and the evening and the morning were the first day','and god said let there be a firmament in the midst of the waters'],
  NIV: ['in the beginning god created the heavens and the earth','now the earth was formless and empty darkness was over the surface of the deep','and the spirit of god was hovering over the waters','and god said let there be light and there was light','god saw that the light was good and he separated the light from the darkness','god called the light day and the darkness he called night','and there was evening and there was morning the first day','and god said let there be a vault between the waters'],
  BBE: ['at the first god made the heaven and the earth','the earth was without form and empty and darkness was over the deep','and the spirit of god was moving over the face of the waters','and god said let there be light and there was light','and god saw the light was good and a division was made by god between the light and the dark','and god gave the light the name of day and the dark he named night','and there was evening and there was morning the first day','and god said let there be a division of the waters'],
  DR:  ['in the beginning god created heaven and earth','and the earth was void and empty and darkness was upon the face of the deep','and the spirit of god moved over the waters','and god said be light made and light was made','and god saw the light that it was good and he divided the light from the darkness','and he called the light day and the darkness night','and there was evening and morning one day','and god said let there be a firmament made amidst the waters'],
  GNV: ['in the beginning god created the heaven and the earth','and the earth was without forme and void and darkenes was vpon the depe','and the spirite of god moued vpon the waters','and god said let there be light and there was light','and god saw the light that it was good and god separated the light from the darkenes','and god called the light day and the darkenes night','so the euening and the morning were the first day','againe god said let there be a firmament in the middes of the waters'],
  WYC: ['in the bigynnyng god made of nouyt heuene and erthe','forsothe the erthe was idel and voide and derknessis weren on the face of depthe','and the spirit of the lord was borun on the watris','and god seide be maad liyt and liyt was maad','and god seiy the liyt that it was good and he departide the liyt fro derknessis','and he clepide the liyt dai and the derknessis nyyt','and the euentid and morwetid was maad o dai','and god seide be maad a firmament in the myddis of watris'],
}

export const WEB_TEXT = COL_TEXTS.WEB

export function getColT(id, si) {
  return (COL_TEXTS[id] || WEB_TEXT)[si] || ''
}

export const WITNESSES = [
  { id:'WEB',  name:'World English Bible',           year:2000, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text, Septuagint' },
  { id:'ASV',  name:'American Standard Version',     year:1901, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text' },
  { id:'AVW',  name:'A Voice in the Wilderness',     year:2004, origin:[39.5,-98.4],  affiliation:'Evangelical', source:'Masoretic Text' },
  { id:'BBE',  name:'Bible In Basic English',        year:1949, origin:[51.5,-0.1],   affiliation:'Protestant',  source:'Masoretic Text' },
  { id:'BISH', name:"Bishop's Bible",                year:1568, origin:[51.5,-0.1],   affiliation:'Anglican',    source:'Hebrew, Greek' },
  { id:'COV',  name:'Coverdale Bible',               year:1535, origin:[51.5,-0.1],   affiliation:'Protestant',  source:'Latin Vulgate' },
  { id:'CPDV', name:'Catholic Public Domain Version',year:2009, origin:[39.5,-98.4],  affiliation:'Catholic',    source:'Latin Vulgate' },
  { id:'DR',   name:'Douay-Rheims Bible',            year:1609, origin:[50.6,3.1],    affiliation:'Catholic',    source:'Latin Vulgate' },
  { id:'DRC',  name:'Douay-Rheims Challoner Bible',  year:1750, origin:[51.5,-0.1],   affiliation:'Catholic',    source:'Latin Vulgate' },
  { id:'ERV',  name:'English Revised Version',       year:1885, origin:[51.5,-0.1],   affiliation:'Protestant',  source:'Masoretic Text, Septuagint' },
  { id:'ESV',  name:'ESV English Standard Version',  year:2001, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text, Septuagint' },
  { id:'GB',   name:'Great Bible',                   year:1539, origin:[51.5,-0.1],   affiliation:'Anglican',    source:'Hebrew, Greek' },
  { id:'GNV',  name:'Geneva Bible',                  year:1560, origin:[46.2,6.1],    affiliation:'Protestant',  source:'Hebrew, Greek' },
  { id:'GW',   name:"God's Word Translation",        year:1995, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text, Septuagint' },
  { id:'KJV',  name:'King James Version',            year:1611, origin:[51.5,-0.1],   affiliation:'Anglican',    source:'Hebrew, Greek' },
  { id:'MAT',  name:"Matthew's Bible",               year:1537, origin:[51.5,-0.1],   affiliation:'Protestant',  source:'Hebrew, Greek' },
  { id:'NIV',  name:'New International Version',     year:1978, origin:[39.5,-98.4],  affiliation:'Evangelical', source:'Masoretic Text, Septuagint' },
  { id:'NKJV', name:'New King James Version',        year:1982, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text' },
  { id:'NLV',  name:'New Life Version',              year:1969, origin:[39.5,-98.4],  affiliation:'Evangelical', source:'Masoretic Text' },
  { id:'RSV',  name:'Revised Standard Version',      year:1952, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text, Septuagint' },
  { id:'SLT',  name:'Smith Literal Translation',     year:1876, origin:[39.5,-98.4],  affiliation:'Protestant',  source:'Masoretic Text' },
  { id:'TYN',  name:'Tyndale Bible',                 year:1526, origin:[51.5,-0.1],   affiliation:'Protestant',  source:'Hebrew, Greek' },
  { id:'WYC',  name:'Wycliffe Bible',                year:1382, origin:[51.5,-0.1],   affiliation:'Catholic',    source:'Latin Vulgate' },
  { id:'YLT',  name:"Young's Literal Translation",   year:1862, origin:[55.8,-4.2],   affiliation:'Protestant',  source:'Masoretic Text' },
  { id:'CB',   name:'Complete Bible',                year:1535, origin:[51.5,-0.1],   affiliation:'Protestant',  source:'Hebrew, Greek, Latin Vulgate' },
  { id:'AVV',  name:'Authorized Version',            year:1769, origin:[51.5,-0.1],   affiliation:'Anglican',    source:'Hebrew, Greek' },
]

export const VARIANT_WORDS = [
  'firkins','cubits','ephah','homer','gerah','shekel','talent','formless',
  'sackbut','psaltery','nard','chaldees','sabaoth','jehoshaphat',
  'mene, mene, tekel','shiggaion','al-taschith','mahalath','gittith',
  'aijeleth shahar','maschil','selah','hosanna','bethlehem','nazareth',
  'galilee','judea','samaria','pharisee','sadducee','sanhedrin',
]
