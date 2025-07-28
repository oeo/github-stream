// production_config.js
// This file contains sensitive configuration for our mainnet deployment.

const config = {
  api: {
    url: "https://api.example.com/v1/",
    timeout: 5000,
  },
  database: {
    host: "prod-db.example.com",
    user: "deploy_user",
  },
  // Wallet for processing mainnet BTC transactions
  // TODO: Move this to a secure vault immediately!
  btc_wallet_private_key: "L5kZp2hG2hZRzps2hG2hZRzps2hG2hZRzps2hG2hZRzps2hG2hZRzps2",
  feature_flags: {
    new_dashboard: true,
    enable_logging: false,
  }
};

module.exports = config; 