# 🚨 GenAIベース サーバーレス無人障害検知・対応自動化システム (PoC)

![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20API%20Gateway%20%7C%20S3-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![AI](https://img.shields.io/badge/GenAI-Amazon%20Bedrock%20(Claude%204.6)-blue?style=for-the-badge)
![API](https://img.shields.io/badge/Integration-Slack%20%7C%20Twilio-4A154B?style=for-the-badge)

## 1. プロジェクト概要 (Executive Summary)
本プロジェクトは、クラウドインフラ運用中に発生する夜間の監視空白および障害伝播の遅延問題を解決するために考案された、イベント駆動型（Event-Driven）の自動障害対応システムです。

従来の手動監視方式から脱却し、障害発生時に **Amazon Bedrock（Claude 4.6 Sonnet）** がマニュアルを分析し、状況に応じた丁寧なビジネス日本語のレポートおよび音声台本を即時作成します。その後、**SlackおよびTwilio API** を通じて担当者へ超高速で伝播する100%サーバーレスパイプラインを構築しました。

## 2. 解決したビジネス上の課題 (Pain Point)
- **初動認知および伝播の遅延：** 深夜帯にCRITICAL障害が発生した際、担当者がアラームを確認し、マニュアルを探して状況を把握するために発生する物理的な時間のロス。
- **言語の壁によるリスク：** 緊急時に外国人エンジニアがビジネス日本語の敬語で正確な障害状況および対応ガイドを作成しなければならない心理的・時間的負担。

## 3. システムアーキテクチャ (Architecture)
- **精密トリガー (API Gateway)：** 外部監視ソリューションまたはモバイルリモコンが障害信号(JSON)を送信。
- **マニュアルクエリ (Amazon S3)：** AWS Lambdaが稼働し、S3に保存された障害マニュアルDBから過去の解決履歴を参照。
- **GenAI頭脳レイヤー (Amazon Bedrock)：** Claude 4.6モデルがマニュアルを分析し、Slack本文と20秒間のIVR電話台本を作成。
- **マルチチャネル伝播 (Slack & Twilio)：** Python標準HTTPライブラリにより、Slackへのリアルタイムテキスト報告とスマートフォンへのアウトバウンド日本語音声通話を同時送信。

## 4. 差別化ポイントおよびコスト最適化 (Cost Optimization)
単なるAI連携にとどまらず、実際のエンタープライズ環境におけるインフラコストと業務効率を考慮した3段階のシナリオルーティングロジックを適用しました。
- 🚨 **CRITICAL (フルコース)：** AI台本作成 ＋ Slack詳細報告 ＋ Twilio音声電話ブリーフィング発信
- ⚠️ **WARNING (一般注意)：** AI台本作成 ＋ Slack報告（音声電話は遮断）
- 🔍 **SEIKAN (静観・監視除外)：** 高価なBedrock(LLM)呼び出しを根元から遮断し、0.01秒で自動停止およびSlackアラート送信。 **（不要なAIコスト$0を実現）**

## 5. デモ動画 (Demo)
[*(※後日、スマートフォンでのデモ動画をここに追加する予定です)*](https://youtu.be/rAMN6wF3vDw)
