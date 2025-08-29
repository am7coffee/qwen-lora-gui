# slackのincoming webhook URL取得簡易ガイド
2025/8/29時点

SlackのIncoming Webhook URLは、外部のアプリケーションからSlackへメッセージを自動的に投稿するために必要なURLです。Slack APIサイトでのアプリ作成を通じて取得できます。以下に、SlackへのログインからWebhook URLを取得するまでの手順を解説します。

### 1. Slackへのサインインとワークスペースの準備

まず、Slack APIを利用するために、お使いのSlackアカウントでサインインし、開発用のワークスペースを準備します。

* **Slackにサインインする**
Webブラウザで `slack.com/signin` にアクセスします。メールアドレス、Googleアカウント、またはAppleアカウントを使用してサインインできます。
* **開発用ワークスペースの準備**
すでに通知を飛ばしたいワークスペースがある場合はそれを使用します。ない場合は、テスト用に新しいワークスペースを作成することもできます。


### 2. Incoming Webhook URLの取得手順

次に、Slackアプリを作成し、Incoming Webhookを有効化してURLを取得します。

* **ステップ1：Slackアプリを新規作成する**

1. Slack APIの「[Your Apps](https://api.slack.com/apps)」ページにアクセスし、「Create New App」をクリックします。
2. 「From scratch」を選択します。
3. 「App Name」に任意のアプリ名を入力し、「Pick a workspace to develop your app in」で通知を送信したいワークスペースを選択して、「Create App」をクリックします。
* **ステップ2：Incoming Webhooksを有効化する**
アプリの管理画面が表示されたら、左側のメニューの「Features」セクションにある「Incoming Webhooks」を選択します。その後、表示される画面で「Activate Incoming Webhooks」のスイッチをオンにします。
* **ステップ3：Webhook URLを生成する**

1. Incoming Webhooksを有効にすると表示される「Add New Webhook to Workspace」ボタンをクリックします。
2. 通知を投稿したいチャンネルを選択し、「許可する」をクリックします。
3. アプリの管理画面に戻ると、「Webhook URLs for Your Workspace」セクションに新しいWebhook URLが生成されています。このURLをコピーして使用します。URLは `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX` のような形式です。

このWebhook URLは秘密の情報ですので、公開リポジトリなどで外部に漏洩しないよう注意してください。