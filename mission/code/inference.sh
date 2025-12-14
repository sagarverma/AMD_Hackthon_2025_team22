sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1

lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM1 \
  --robot.id=versag_follower_arm \
  --robot.cameras="{top: {type: opencv, index_or_path: 3, width: 640, height: 480, fps: 30}, side: {type: opencv, index_or_path: 5, width: 640, height: 480, fps: 30}}" \
  --dataset.single_task="Pick pen from source position and place it anywhere" \
  --dataset.repo_id=versag/eval_so101_act_pick_pen \
  --dataset.root=${PWD}/eval_lerobot_dataset/ \
  --dataset.episode_time_s=20 \
  --dataset.num_episodes=1 \
  --policy.path=${PWD}/weights/so101_act_pick_pen \
  --dataset.push_to_hub=false