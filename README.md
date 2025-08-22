# Discord MBTI相性診断Bot

## 概要

**Discord内でMBTIタイプ（性格診断タイプ）に基づく“相性の良いユーザー”を自動検索＆DM通知できるBot**です。  
OpenAI（GPT）やGeminiにも接続し、診断体験をパネル＋ボタンUIで完結。  
履歴やタイプ情報はPostgreSQLに保存、誰でも直感的に使えるよう設計しています。

- **MBTIタイプごとの「相性診断」パネルをワンタッチ表示**
- 相性の良いタイプを自動抽出し、ジャンプリンク付きでDM送信
- サーバーの役職・履歴・AI連携で柔軟なタイプ判定が可能

---

## 主な特徴

- **1クリックで「相性診断パネル」生成**（スラッシュコマンド対応）
- **相性判定ロジックはカスタムで調整OK**
- **ユーザーのMBTIタイプは「ロール」or「履歴」から自動判別**
- **診断結果をDMで個別通知**（ジャンプリンク付きで即プロフィール参照可）
- **OpenAI・Gemini APIに接続済み**（高度な応答にも拡張可能）
- **PostgreSQLで履歴管理・拡張性重視の設計**
- **Bot管理や拡張のための環境変数運用**

---

## 技術スタック・設計

- **Python3.11 / discord.py / asyncpg / openai / google-generativeai**
- **PostgreSQL（DBプール管理／タイプ履歴保存）**
- **スラッシュコマンド × ボタンView × Embed UI**
- **MBTIロール/履歴自動判別 ＋ 柔軟なチャンネル・ユーザーID指定**
- **（Optional）AI応答・分析機能に今後拡張可**

---

## 使い方・セットアップ

1. このリポジトリをクローン  
   ```sh
   git clone https://github.com/あなたのユーザー名/リポジトリ名.git
DISCORD_BOT_TOKEN=xxx
OPENAI_API_KEY=xxx      # （任意、GPT利用時のみ）
GEMINI_API_KEY=xxx      # （任意、Gemini利用時のみ）
DATABASE_URL=postgresql://xxx
DUO_CHANNEL_ID=123456789012345678
MBTI_HISTORY_CHANNELS=1111111111111,2222222222222
MBTI_HISTORY_SCAN_LIMIT=200
依存パッケージをインストール

pip install -r requirements.txt


サーバーにBotを招待し、
/diagnosis スラッシュコマンドで「相性診断パネル」を表示
あとはボタンを押すだけで診断結果がDMに届きます！

作者 しゅん K.
