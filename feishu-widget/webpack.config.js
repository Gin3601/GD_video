const path = require("path");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const webpack = require("webpack");
const appConfig = require("./app.json");

const isDevelopment = process.env.NODE_ENV === "development";

class FeishuDocsAddonConfigPlugin {
  apply(compiler) {
    compiler.hooks.thisCompilation.tap("FeishuDocsAddonConfigPlugin", (compilation) => {
      compilation.hooks.processAssets.tap(
        {
          name: "FeishuDocsAddonConfigPlugin",
          stage: webpack.Compilation.PROCESS_ASSETS_STAGE_ADDITIONAL
        },
        () => {
          const projectConfig = {
            appid: appConfig.appID,
            projectname: appConfig.projectName,
            blocks: ["index"]
          };
          const blockConfig = {
            blockTypeID: appConfig.blockTypeID,
            blockRenderType: "offlineWeb",
            offlineWebConfig: {
              initialHeight: appConfig.initialHeight,
              contributes: appConfig.contributes
            }
          };
          compilation.emitAsset(
            "project.config.json",
            new webpack.sources.RawSource(JSON.stringify(projectConfig, null, 2))
          );
          compilation.emitAsset(
            "index.json",
            new webpack.sources.RawSource(JSON.stringify(blockConfig, null, 2))
          );
        }
      );
    });
  }
}

module.exports = {
  mode: isDevelopment ? "development" : "production",
  entry: {
    index: "./src/main.js"
  },
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "assets/[name].[contenthash:8].js",
    clean: true,
    publicPath: isDevelopment ? "/" : "./"
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [isDevelopment ? "style-loader" : MiniCssExtractPlugin.loader, "css-loader"]
      }
    ]
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: "./src/index.html",
      filename: "index.html",
      chunks: ["index"]
    }),
    new CopyWebpackPlugin({
      patterns: [{ from: "app.json", to: "app.json" }]
    }),
    new FeishuDocsAddonConfigPlugin(),
    ...(!isDevelopment ? [new MiniCssExtractPlugin({ filename: "assets/[name].[contenthash:8].css" })] : [])
  ],
  devServer: {
    host: "0.0.0.0",
    port: 5174,
    hot: true,
    historyApiFallback: true,
    static: {
      directory: path.resolve(__dirname, "dist")
    },
    client: {
      overlay: true
    }
  },
  stats: "errors-warnings"
};
