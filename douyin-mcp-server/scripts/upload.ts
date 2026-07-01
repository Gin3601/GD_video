#!/usr/bin/env npx tsx
/**
 * 抖音视频上传脚本
 * 用法: npx tsx scripts/upload.ts --video <path> --title <title> [options]
 */

import { DouyinUploader } from '../mcp-server/douyin-uploader.js';

interface UploadArgs {
  video: string;
  title: string;
  description?: string;
  tags?: string[];
  headless: boolean;
  autoPublish: boolean;
}

function parseArgs(args: string[]): UploadArgs {
  const result: UploadArgs = {
    video: '',
    title: '',
    headless: false,
    autoPublish: true,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    switch (arg) {
      case '--video':
      case '-v':
        if (next) {
          result.video = next;
          i++;
        }
        break;
      case '--title':
      case '-t':
        if (next) {
          result.title = next;
          i++;
        }
        break;
      case '--description':
      case '-d':
        if (next) {
          result.description = next;
          i++;
        }
        break;
      case '--tags':
        if (next) {
          result.tags = next.split(',').map((t) => t.trim());
          i++;
        }
        break;
      case '--headless':
        result.headless = true;
        break;
      case '--no-publish':
        result.autoPublish = false;
        break;
    }
  }

  return result;
}

function printUsage() {
  console.log(`
Usage: npx tsx scripts/upload.ts --video <path> --title <title> [options]

Required:
  --video, -v <path>       Path to video file
  --title, -t <title>      Video title

Optional:
  --description, -d <text> Video description
  --tags <tag1,tag2>       Comma-separated tags
  --headless               Run browser in headless mode
  --no-publish             Save as draft instead of publishing

Example:
  npx tsx scripts/upload.ts --video "./video.mp4" --title "My Video" --tags "fun,daily"
`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args.video || !args.title) {
    console.error('❌ Error: --video and --title are required\n');
    printUsage();
    process.exit(1);
  }

  const uploader = new DouyinUploader();

  console.log('🚀 Starting Douyin upload...');
  console.log(`   Video: ${args.video}`);
  console.log(`   Title: ${args.title}`);
  if (args.description) console.log(`   Description: ${args.description}`);
  if (args.tags) console.log(`   Tags: ${args.tags.join(', ')}`);
  console.log(`   Auto-publish: ${args.autoPublish}`);
  console.log('');

  const result = await uploader.uploadVideo({
    videoPath: args.video,
    title: args.title,
    description: args.description,
    tags: args.tags,
    headless: args.headless,
    autoPublish: args.autoPublish,
  });

  if (result.success) {
    console.log(`✅ Video upload ${result.published ? 'and publish ' : ''}successful!`);
    console.log(`   Title: ${result.title}`);
    console.log(`   Status: ${result.status}`);
    process.exit(0);
  } else {
    console.log(`❌ Upload failed: ${result.error}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
