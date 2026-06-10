"""ILP 기반 직무역량 과목 추천 (설계: docs/ILP_추천시스템_설계.md).

transcript 모듈과는 DB(student*/course* 테이블)로만 연결되며 직접 import 의존이 없다.
구성: data(DB 로더) · params(σ/gap/Score/need 사전계산) · model(PuLP 2단계 ILP)
     · recommend(재사용 서비스 진입점 recommend()) · cli(실험용 래퍼).
프로토타입(웹/API)은 cli가 아니라 recommend.recommend()를 직접 호출한다.
"""
