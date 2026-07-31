using UnityEngine;

namespace Vibe21.Twin
{
    /// <summary>Free-fly / drone-style camera for site inspection.</summary>
    [RequireComponent(typeof(Camera))]
    public class DroneFlyCamera : MonoBehaviour
    {
        public float moveSpeed = 18f;
        public float boostMultiplier = 3f;
        public float lookSensitivity = 2.2f;
        public float minPitch = -89f;
        public float maxPitch = 89f;
        public bool requireRightMouseLook = true;

        float _yaw;
        float _pitch;

        void Start()
        {
            var e = transform.eulerAngles;
            _yaw = e.y;
            _pitch = e.x > 180f ? e.x - 360f : e.x;
        }

        void Update()
        {
            bool looking = !requireRightMouseLook || Input.GetMouseButton(1);
            if (looking)
            {
                _yaw += Input.GetAxis("Mouse X") * lookSensitivity;
                _pitch -= Input.GetAxis("Mouse Y") * lookSensitivity;
                _pitch = Mathf.Clamp(_pitch, minPitch, maxPitch);
                transform.rotation = Quaternion.Euler(_pitch, _yaw, 0f);
            }

            float boost = Input.GetKey(KeyCode.LeftShift) ? boostMultiplier : 1f;
            Vector3 dir = Vector3.zero;
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) dir += transform.forward;
            if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) dir -= transform.forward;
            if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) dir -= transform.right;
            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) dir += transform.right;
            if (Input.GetKey(KeyCode.E) || Input.GetKey(KeyCode.Space)) dir += Vector3.up;
            if (Input.GetKey(KeyCode.Q) || Input.GetKey(KeyCode.LeftControl)) dir -= Vector3.up;
            if (dir.sqrMagnitude > 0f)
                transform.position += dir.normalized * (moveSpeed * boost * Time.deltaTime);
        }
    }
}
