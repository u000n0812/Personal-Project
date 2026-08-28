export type TarotCard = {
  name: string;
  keyword: string;
  uprightMeaning: string;
  reversedMeaning: string;
};

export const TAROT_DECK: TarotCard[] = [
  { name: "바보 (The Fool)", keyword: "새로운 시작", uprightMeaning: "두려움 없이 첫걸음을 내딛는 순수한 용기", reversedMeaning: "충동적인 선택으로 방향을 잃기 쉬운 상태" },
  { name: "마법사 (The Magician)", keyword: "실행력", uprightMeaning: "가진 재능과 자원을 모아 원하는 걸 현실로 만드는 힘", reversedMeaning: "능력은 있지만 확신이 없어 머뭇거리는 상태" },
  { name: "여사제 (The High Priestess)", keyword: "직관", uprightMeaning: "겉으로 드러나지 않은 진실을 조용히 알아차리는 힘", reversedMeaning: "내면의 목소리를 애써 외면하고 있는 상태" },
  { name: "여황제 (The Empress)", keyword: "풍요", uprightMeaning: "돌봄과 여유 속에서 자연스럽게 자라나는 결실", reversedMeaning: "스스로를 돌보지 못해 지쳐 있는 상태" },
  { name: "황제 (The Emperor)", keyword: "안정", uprightMeaning: "원칙과 구조로 상황을 단단하게 잡아가는 힘", reversedMeaning: "지나친 통제로 스스로를 옥죄는 상태" },
  { name: "교황 (The Hierophant)", keyword: "조언", uprightMeaning: "믿을 만한 사람이나 원칙에게서 얻는 방향성", reversedMeaning: "익숙한 방식에서 벗어나고 싶은 마음" },
  { name: "연인 (The Lovers)", keyword: "선택", uprightMeaning: "마음이 이끄는 대로 내리는 진심 어린 선택", reversedMeaning: "우유부단함으로 결정을 미루고 있는 상태" },
  { name: "전차 (The Chariot)", keyword: "추진력", uprightMeaning: "여러 갈래의 힘을 하나로 모아 목표로 나아가는 기세", reversedMeaning: "방향을 잃고 제자리에서 힘만 쓰는 상태" },
  { name: "힘 (Strength)", keyword: "인내", uprightMeaning: "부드러움으로 어려운 상황을 다독여 이겨내는 힘", reversedMeaning: "스스로에 대한 확신이 흔들리는 상태" },
  { name: "은둔자 (The Hermit)", keyword: "성찰", uprightMeaning: "잠시 멈춰 혼자만의 시간에서 답을 찾는 지혜", reversedMeaning: "고립감 속에 혼자 갇혀 있는 느낌" },
  { name: "운명의 수레바퀴 (Wheel of Fortune)", keyword: "전환점", uprightMeaning: "흐름이 자연스럽게 바뀌며 찾아오는 기회", reversedMeaning: "예상치 못한 변화에 흔들리는 시기" },
  { name: "정의 (Justice)", keyword: "균형", uprightMeaning: "공정한 판단으로 상황을 제자리로 돌려놓는 힘", reversedMeaning: "치우친 결정으로 균형이 무너진 상태" },
  { name: "매달린 사람 (The Hanged Man)", keyword: "기다림", uprightMeaning: "당장 움직이지 않고 다른 관점을 받아들이는 여유", reversedMeaning: "제자리걸음에 답답함이 쌓이는 상태" },
  { name: "죽음 (Death)", keyword: "마무리", uprightMeaning: "한 시기를 정리하고 다음으로 넘어가는 자연스러운 변화", reversedMeaning: "끝내야 할 것을 붙잡고 놓지 못하는 상태" },
  { name: "절제 (Temperance)", keyword: "조화", uprightMeaning: "서로 다른 것들을 알맞게 섞어 균형을 찾는 힘", reversedMeaning: "과하거나 부족해 균형이 깨진 상태" },
  { name: "악마 (The Devil)", keyword: "속박", uprightMeaning: "익숙한 습관이나 관계에 묶여 있음을 알아차리는 순간", reversedMeaning: "그 굴레에서 벗어나려는 움직임이 시작됨" },
  { name: "탑 (The Tower)", keyword: "급변", uprightMeaning: "낡은 틀이 무너지며 찾아오는 갑작스러운 전환", reversedMeaning: "충격을 최소화하려 애쓰고 있는 상태" },
  { name: "별 (The Star)", keyword: "희망", uprightMeaning: "힘든 시간을 지나 다시 찾아오는 잔잔한 희망", reversedMeaning: "믿음이 흔들리며 확신이 옅어진 상태" },
  { name: "달 (The Moon)", keyword: "불확실함", uprightMeaning: "명확하지 않은 상황 속에서 직감에 기대야 하는 시기", reversedMeaning: "혼란이 서서히 걷히며 실마리가 보이는 시점" },
  { name: "태양 (The Sun)", keyword: "활력", uprightMeaning: "숨김없이 밝게 드러나는 성취와 기쁨", reversedMeaning: "밝은 기운이 아직은 살짝 가려진 상태" },
  { name: "심판 (Judgement)", keyword: "재정비", uprightMeaning: "지난 시간을 돌아보고 스스로를 다시 세우는 순간", reversedMeaning: "과거의 판단을 계속 곱씹으며 머뭇거리는 상태" },
  { name: "세계 (The World)", keyword: "완성", uprightMeaning: "한 사이클을 잘 마무리하고 다음 문을 여는 시점", reversedMeaning: "마무리까지 조금 더 시간이 필요한 상태" },
];
