// 状态同步功能测试脚本
// 在浏览器控制台中运行此脚本测试WebSocket状态同步

// 测试WebSocket连接
function testWebSocketConnection() {
  console.log('开始测试WebSocket状态同步...');

  // 模拟WebSocket连接
  const ws = new WebSocket('ws://localhost:8000/sim/ws');

  ws.onopen = function(event) {
    console.log('✅ WebSocket连接已建立');
    // 发送ping消息
    ws.send(JSON.stringify({ type: 'ping', data: { client: 'test-client' } }));
  };

  ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('📨 收到消息:', message.type, message);

    if (message.type === 'welcome') {
      console.log('✅ 服务器欢迎消息接收成功');
    } else if (message.type === 'state_update') {
      console.log('✅ 状态更新消息接收成功');
      console.log('关节角度:', message.data.qpos);
      console.log('关节速度:', message.data.qvel);
    } else if (message.type === 'pong') {
      console.log('✅ Ping-Pong测试成功');
    }
  };

  ws.onclose = function(event) {
    console.log('❌ WebSocket连接已关闭:', event.code, event.reason);
  };

  ws.onerror = function(error) {
    console.error('❌ WebSocket错误:', error);
  };

  // 5秒后自动关闭连接
  setTimeout(() => {
    ws.close();
    console.log('测试完成，连接已关闭');
  }, 5000);

  return ws;
}

// 运行测试
if (typeof window !== 'undefined') {
  // 浏览器环境
  window.testStateSync = testWebSocketConnection;
  console.log('运行 window.testStateSync() 开始测试');
} else {
  // Node.js环境
  testWebSocketConnection();
}
