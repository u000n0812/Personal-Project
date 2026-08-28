export type TarotSuit = "wands" | "cups" | "swords" | "pentacles";

export type TarotCard = {
  name: string;
  keyword: string;
  uprightMeaning: string;
  reversedMeaning: string;
  arcana: "major" | "minor";
  suit?: TarotSuit;
};

export const SUIT_LABEL: Record<TarotSuit, string> = {
  wands: "완드",
  cups: "컵",
  swords: "소드",
  pentacles: "펜타클",
};

/** 메이저 아르카나 22장 — 삶의 큰 흐름과 전환을 다룬다. */
const MAJOR: TarotCard[] = [
  { name: "바보 (The Fool)", keyword: "새로운 시작", uprightMeaning: "두려움 없이 첫걸음을 내딛는 순수한 용기", reversedMeaning: "충동적인 선택으로 방향을 잃기 쉬운 상태", arcana: "major" },
  { name: "마법사 (The Magician)", keyword: "실행력", uprightMeaning: "가진 재능과 자원을 모아 원하는 걸 현실로 만드는 힘", reversedMeaning: "능력은 있지만 확신이 없어 머뭇거리는 상태", arcana: "major" },
  { name: "여사제 (The High Priestess)", keyword: "직관", uprightMeaning: "겉으로 드러나지 않은 진실을 조용히 알아차리는 힘", reversedMeaning: "내면의 목소리를 애써 외면하고 있는 상태", arcana: "major" },
  { name: "여황제 (The Empress)", keyword: "풍요", uprightMeaning: "돌봄과 여유 속에서 자연스럽게 자라나는 결실", reversedMeaning: "스스로를 돌보지 못해 지쳐 있는 상태", arcana: "major" },
  { name: "황제 (The Emperor)", keyword: "안정", uprightMeaning: "원칙과 구조로 상황을 단단하게 잡아가는 힘", reversedMeaning: "지나친 통제로 스스로를 옥죄는 상태", arcana: "major" },
  { name: "교황 (The Hierophant)", keyword: "조언", uprightMeaning: "믿을 만한 사람이나 원칙에게서 얻는 방향성", reversedMeaning: "익숙한 방식에서 벗어나고 싶은 마음", arcana: "major" },
  { name: "연인 (The Lovers)", keyword: "선택", uprightMeaning: "마음이 이끄는 대로 내리는 진심 어린 선택", reversedMeaning: "우유부단함으로 결정을 미루고 있는 상태", arcana: "major" },
  { name: "전차 (The Chariot)", keyword: "추진력", uprightMeaning: "여러 갈래의 힘을 하나로 모아 목표로 나아가는 기세", reversedMeaning: "방향을 잃고 제자리에서 힘만 쓰는 상태", arcana: "major" },
  { name: "힘 (Strength)", keyword: "인내", uprightMeaning: "부드러움으로 어려운 상황을 다독여 이겨내는 힘", reversedMeaning: "스스로에 대한 확신이 흔들리는 상태", arcana: "major" },
  { name: "은둔자 (The Hermit)", keyword: "성찰", uprightMeaning: "잠시 멈춰 혼자만의 시간에서 답을 찾는 지혜", reversedMeaning: "고립감 속에 혼자 갇혀 있는 느낌", arcana: "major" },
  { name: "운명의 수레바퀴 (Wheel of Fortune)", keyword: "전환점", uprightMeaning: "흐름이 자연스럽게 바뀌며 찾아오는 기회", reversedMeaning: "예상치 못한 변화에 흔들리는 시기", arcana: "major" },
  { name: "정의 (Justice)", keyword: "균형", uprightMeaning: "공정한 판단으로 상황을 제자리로 돌려놓는 힘", reversedMeaning: "치우친 결정으로 균형이 무너진 상태", arcana: "major" },
  { name: "매달린 사람 (The Hanged Man)", keyword: "기다림", uprightMeaning: "당장 움직이지 않고 다른 관점을 받아들이는 여유", reversedMeaning: "제자리걸음에 답답함이 쌓이는 상태", arcana: "major" },
  { name: "죽음 (Death)", keyword: "마무리", uprightMeaning: "한 시기를 정리하고 다음으로 넘어가는 자연스러운 변화", reversedMeaning: "끝내야 할 것을 붙잡고 놓지 못하는 상태", arcana: "major" },
  { name: "절제 (Temperance)", keyword: "조화", uprightMeaning: "서로 다른 것들을 알맞게 섞어 균형을 찾는 힘", reversedMeaning: "과하거나 부족해 균형이 깨진 상태", arcana: "major" },
  { name: "악마 (The Devil)", keyword: "속박", uprightMeaning: "익숙한 습관이나 관계에 묶여 있음을 알아차리는 순간", reversedMeaning: "그 굴레에서 벗어나려는 움직임이 시작됨", arcana: "major" },
  { name: "탑 (The Tower)", keyword: "급변", uprightMeaning: "낡은 틀이 무너지며 찾아오는 갑작스러운 전환", reversedMeaning: "충격을 최소화하려 애쓰고 있는 상태", arcana: "major" },
  { name: "별 (The Star)", keyword: "희망", uprightMeaning: "힘든 시간을 지나 다시 찾아오는 잔잔한 희망", reversedMeaning: "믿음이 흔들리며 확신이 옅어진 상태", arcana: "major" },
  { name: "달 (The Moon)", keyword: "불확실함", uprightMeaning: "명확하지 않은 상황 속에서 직감에 기대야 하는 시기", reversedMeaning: "혼란이 서서히 걷히며 실마리가 보이는 시점", arcana: "major" },
  { name: "태양 (The Sun)", keyword: "활력", uprightMeaning: "숨김없이 밝게 드러나는 성취와 기쁨", reversedMeaning: "밝은 기운이 아직은 살짝 가려진 상태", arcana: "major" },
  { name: "심판 (Judgement)", keyword: "재정비", uprightMeaning: "지난 시간을 돌아보고 스스로를 다시 세우는 순간", reversedMeaning: "과거의 판단을 계속 곱씹으며 머뭇거리는 상태", arcana: "major" },
  { name: "세계 (The World)", keyword: "완성", uprightMeaning: "한 사이클을 잘 마무리하고 다음 문을 여는 시점", reversedMeaning: "마무리까지 조금 더 시간이 필요한 상태", arcana: "major" },
];

/** 완드 — 열정, 행동, 창조. 불의 원소. */
const WANDS: TarotCard[] = [
  { name: "완드 에이스", keyword: "영감", uprightMeaning: "하고 싶은 일이 떠오르며 의욕이 솟는 출발점", reversedMeaning: "의욕은 있는데 어디서부터 시작할지 막막한 상태", arcana: "minor", suit: "wands" },
  { name: "완드 2", keyword: "계획", uprightMeaning: "멀리 내다보며 다음 행보를 구상하는 시기", reversedMeaning: "계획만 세우다 실행을 미루고 있는 상태", arcana: "minor", suit: "wands" },
  { name: "완드 3", keyword: "확장", uprightMeaning: "준비한 일이 바깥으로 뻗어나가기 시작함", reversedMeaning: "기대만큼 진전이 없어 조바심이 나는 시기", arcana: "minor", suit: "wands" },
  { name: "완드 4", keyword: "축하", uprightMeaning: "한 단계를 마치고 함께 기뻐하는 안정된 순간", reversedMeaning: "겉으로는 평온하나 속으로 불안이 남아 있음", arcana: "minor", suit: "wands" },
  { name: "완드 5", keyword: "경쟁", uprightMeaning: "여러 의견이 부딪히며 에너지가 흩어지는 상황", reversedMeaning: "불필요한 다툼을 피하고 정리하려는 움직임", arcana: "minor", suit: "wands" },
  { name: "완드 6", keyword: "인정", uprightMeaning: "노력이 눈에 띄고 주변의 인정을 받는 시기", reversedMeaning: "성과에 비해 알아주는 사람이 적어 서운한 마음", arcana: "minor", suit: "wands" },
  { name: "완드 7", keyword: "방어", uprightMeaning: "자기 자리를 지키기 위해 버텨내는 뚝심", reversedMeaning: "계속 방어만 하다 지쳐가는 상태", arcana: "minor", suit: "wands" },
  { name: "완드 8", keyword: "속도", uprightMeaning: "일이 빠르게 진행되며 소식이 몰려오는 시기", reversedMeaning: "진행이 자꾸 지연되며 답답해지는 상황", arcana: "minor", suit: "wands" },
  { name: "완드 9", keyword: "끈기", uprightMeaning: "지쳤지만 마지막 고비를 버텨내는 힘", reversedMeaning: "경계심이 지나쳐 스스로를 소모하는 상태", arcana: "minor", suit: "wands" },
  { name: "완드 10", keyword: "부담", uprightMeaning: "책임을 혼자 짊어지고 묵묵히 감당하는 시기", reversedMeaning: "짐을 내려놓고 나눠야 할 때임을 깨달음", arcana: "minor", suit: "wands" },
  { name: "완드 페이지", keyword: "호기심", uprightMeaning: "새로운 관심사에 설레며 뛰어들 준비가 됨", reversedMeaning: "흥미가 금세 식어 오래 가지 못하는 상태", arcana: "minor", suit: "wands" },
  { name: "완드 나이트", keyword: "돌진", uprightMeaning: "망설임 없이 행동으로 옮기는 과감함", reversedMeaning: "성급함이 앞서 실수가 생기기 쉬운 시기", arcana: "minor", suit: "wands" },
  { name: "완드 퀸", keyword: "당당함", uprightMeaning: "자기다움을 잃지 않고 주위를 이끄는 매력", reversedMeaning: "자신감이 흔들려 위축되어 있는 상태", arcana: "minor", suit: "wands" },
  { name: "완드 킹", keyword: "리더십", uprightMeaning: "큰 그림을 그리고 사람을 움직이는 결단력", reversedMeaning: "고집이 세져 주변 의견을 놓치는 상태", arcana: "minor", suit: "wands" },
];

/** 컵 — 감정, 관계, 사랑. 물의 원소. */
const CUPS: TarotCard[] = [
  { name: "컵 에이스", keyword: "새로운 마음", uprightMeaning: "감정이 새롭게 열리며 따뜻함이 차오르는 시작", reversedMeaning: "마음을 열고 싶지만 아직 조심스러운 상태", arcana: "minor", suit: "cups" },
  { name: "컵 2", keyword: "교감", uprightMeaning: "서로 마음이 통하며 관계가 깊어지는 순간", reversedMeaning: "오해가 쌓여 거리감이 생긴 상태", arcana: "minor", suit: "cups" },
  { name: "컵 3", keyword: "어울림", uprightMeaning: "가까운 사람들과 나누는 즐거움과 위로", reversedMeaning: "겉도는 모임에 마음이 헛헛해지는 시기", arcana: "minor", suit: "cups" },
  { name: "컵 4", keyword: "권태", uprightMeaning: "익숙함에 시들해져 새로움을 못 알아보는 상태", reversedMeaning: "무기력에서 벗어나 다시 관심이 생기기 시작함", arcana: "minor", suit: "cups" },
  { name: "컵 5", keyword: "아쉬움", uprightMeaning: "잃은 것에 마음이 머물러 있는 시기", reversedMeaning: "남아 있는 것으로 시선을 옮기며 회복이 시작됨", arcana: "minor", suit: "cups" },
  { name: "컵 6", keyword: "추억", uprightMeaning: "지난 인연이나 기억에서 얻는 따뜻한 위안", reversedMeaning: "과거에 머물러 지금을 놓치고 있는 상태", arcana: "minor", suit: "cups" },
  { name: "컵 7", keyword: "망설임", uprightMeaning: "선택지가 많아 무엇이 진짜인지 헷갈리는 시기", reversedMeaning: "환상을 걷어내고 현실적인 선택으로 향함", arcana: "minor", suit: "cups" },
  { name: "컵 8", keyword: "떠남", uprightMeaning: "미련을 접고 조용히 다음으로 향하는 결심", reversedMeaning: "떠날지 남을지 사이에서 오래 망설이는 상태", arcana: "minor", suit: "cups" },
  { name: "컵 9", keyword: "만족", uprightMeaning: "바라던 것이 채워지며 마음이 넉넉해지는 시기", reversedMeaning: "겉으로는 채워졌지만 속이 허전한 상태", arcana: "minor", suit: "cups" },
  { name: "컵 10", keyword: "화목", uprightMeaning: "가까운 사람들과 이루는 안정되고 따뜻한 관계", reversedMeaning: "겉모습을 지키느라 속마음을 못 나누는 상태", arcana: "minor", suit: "cups" },
  { name: "컵 페이지", keyword: "설렘", uprightMeaning: "감정이 순수하게 움직이며 새 인연이 다가옴", reversedMeaning: "감정 기복이 커 스스로도 종잡기 어려운 상태", arcana: "minor", suit: "cups" },
  { name: "컵 나이트", keyword: "고백", uprightMeaning: "마음을 솔직하게 전하며 다가서는 용기", reversedMeaning: "말과 마음이 어긋나 진심이 흐려지는 시기", arcana: "minor", suit: "cups" },
  { name: "컵 퀸", keyword: "공감", uprightMeaning: "상대의 마음을 깊이 헤아리는 다정함", reversedMeaning: "남의 감정에 휩쓸려 자기를 잃는 상태", arcana: "minor", suit: "cups" },
  { name: "컵 킹", keyword: "포용", uprightMeaning: "감정을 다스리며 주변을 넉넉히 품는 성숙함", reversedMeaning: "속마음을 감추다 거리감이 생기는 상태", arcana: "minor", suit: "cups" },
];

/** 소드 — 생각, 갈등, 판단. 공기의 원소. */
const SWORDS: TarotCard[] = [
  { name: "소드 에이스", keyword: "명료함", uprightMeaning: "안개가 걷히듯 상황이 또렷하게 이해되는 순간", reversedMeaning: "생각이 엉켜 판단이 서지 않는 상태", arcana: "minor", suit: "swords" },
  { name: "소드 2", keyword: "보류", uprightMeaning: "결정을 미루고 양쪽을 저울질하는 시기", reversedMeaning: "외면하던 문제를 마주하기 시작함", arcana: "minor", suit: "swords" },
  { name: "소드 3", keyword: "상처", uprightMeaning: "아픈 말이나 사실을 마주하게 되는 시기", reversedMeaning: "아물어가는 중이며 회복이 시작됨", arcana: "minor", suit: "swords" },
  { name: "소드 4", keyword: "휴식", uprightMeaning: "잠시 멈추고 몸과 마음을 회복시키는 시간", reversedMeaning: "쉬어야 하는데 계속 밀어붙이는 상태", arcana: "minor", suit: "swords" },
  { name: "소드 5", keyword: "갈등", uprightMeaning: "이겨도 개운하지 않은 다툼이 남는 상황", reversedMeaning: "화해하거나 물러설 준비가 되어감", arcana: "minor", suit: "swords" },
  { name: "소드 6", keyword: "이동", uprightMeaning: "힘든 상황에서 벗어나 조용히 옮겨가는 시기", reversedMeaning: "떠나고 싶지만 발이 묶여 있는 상태", arcana: "minor", suit: "swords" },
  { name: "소드 7", keyword: "요령", uprightMeaning: "정면 승부보다 전략으로 풀어가는 시기", reversedMeaning: "숨긴 것이 드러나거나 솔직해지려는 마음", arcana: "minor", suit: "swords" },
  { name: "소드 8", keyword: "제약", uprightMeaning: "스스로 만든 한계에 갇혀 움직이지 못하는 느낌", reversedMeaning: "매듭이 풀리며 빠져나갈 길이 보이기 시작함", arcana: "minor", suit: "swords" },
  { name: "소드 9", keyword: "걱정", uprightMeaning: "생각이 꼬리를 물며 밤잠을 설치는 시기", reversedMeaning: "걱정의 실체를 확인하며 마음이 가벼워짐", arcana: "minor", suit: "swords" },
  { name: "소드 10", keyword: "마무리", uprightMeaning: "한 상황이 완전히 끝나며 바닥을 딛는 시점", reversedMeaning: "끝을 지나 서서히 일어서는 회복기", arcana: "minor", suit: "swords" },
  { name: "소드 페이지", keyword: "탐색", uprightMeaning: "궁금한 것을 파고들며 배우려는 자세", reversedMeaning: "말이 앞서거나 정보에 휘둘리는 상태", arcana: "minor", suit: "swords" },
  { name: "소드 나이트", keyword: "직진", uprightMeaning: "생각을 곧장 말과 행동으로 옮기는 추진력", reversedMeaning: "서두르다 말이 날카로워지는 시기", arcana: "minor", suit: "swords" },
  { name: "소드 퀸", keyword: "냉철함", uprightMeaning: "감정에 흔들리지 않고 핵심을 짚는 판단력", reversedMeaning: "차가움이 지나쳐 마음의 문을 닫은 상태", arcana: "minor", suit: "swords" },
  { name: "소드 킹", keyword: "원칙", uprightMeaning: "기준을 세우고 공정하게 결정하는 힘", reversedMeaning: "융통성이 없어 관계가 뻣뻣해지는 상태", arcana: "minor", suit: "swords" },
];

/** 펜타클 — 현실, 재물, 건강. 땅의 원소. */
const PENTACLES: TarotCard[] = [
  { name: "펜타클 에이스", keyword: "기회", uprightMeaning: "현실적인 기회나 수입의 실마리가 열리는 시작", reversedMeaning: "좋은 기회를 아직 붙잡지 못하고 있는 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 2", keyword: "조율", uprightMeaning: "여러 일을 요령껏 저울질하며 굴려가는 시기", reversedMeaning: "감당할 일이 많아 균형이 흔들리는 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 3", keyword: "협업", uprightMeaning: "각자의 몫을 맡아 함께 결과를 만드는 시기", reversedMeaning: "역할이 어긋나 손발이 안 맞는 상황", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 4", keyword: "지킴", uprightMeaning: "가진 것을 단단히 지키며 안정을 꾀하는 시기", reversedMeaning: "움켜쥐느라 흐름을 막고 있는 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 5", keyword: "결핍", uprightMeaning: "부족함이나 소외감을 느끼며 버티는 시기", reversedMeaning: "도움의 손길이 보이며 상황이 풀리기 시작함", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 6", keyword: "나눔", uprightMeaning: "주고받음이 균형을 이루며 도움이 오가는 시기", reversedMeaning: "한쪽만 베풀어 관계가 기울어진 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 7", keyword: "기다림", uprightMeaning: "공들인 일의 결실을 참고 기다리는 시기", reversedMeaning: "성과가 더뎌 지치고 회의가 드는 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 8", keyword: "숙련", uprightMeaning: "묵묵히 반복하며 실력을 쌓아가는 시기", reversedMeaning: "같은 일에 매너리즘이 찾아온 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 9", keyword: "자립", uprightMeaning: "스스로의 힘으로 여유를 누리게 되는 시기", reversedMeaning: "겉은 풍족하나 마음이 허전한 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 10", keyword: "기반", uprightMeaning: "오래 쌓인 안정이 가족과 생활을 든든히 받쳐줌", reversedMeaning: "재정이나 가족 문제로 기반이 흔들리는 시기", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 페이지", keyword: "배움", uprightMeaning: "새로운 공부나 일을 착실히 시작하는 시기", reversedMeaning: "계획만 있고 실행이 따르지 않는 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 나이트", keyword: "성실", uprightMeaning: "느려도 꾸준히 밀고 나가는 믿음직한 태도", reversedMeaning: "변화 없이 정체되어 지루해지는 시기", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 퀸", keyword: "살림", uprightMeaning: "현실을 알뜰히 돌보며 주변을 챙기는 힘", reversedMeaning: "챙기는 일에 치여 자기를 잃는 상태", arcana: "minor", suit: "pentacles" },
  { name: "펜타클 킹", keyword: "성취", uprightMeaning: "쌓아온 실력과 자산으로 안정을 이룬 상태", reversedMeaning: "물질에 집착해 여유를 잃어가는 시기", arcana: "minor", suit: "pentacles" },
];

/** 정식 78장 덱. */
export const TAROT_DECK: TarotCard[] = [
  ...MAJOR,
  ...WANDS,
  ...CUPS,
  ...SWORDS,
  ...PENTACLES,
];
