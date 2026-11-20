import UIKit

final class ProfileView: UIView {
    private let titleLabel = UILabel()
    private let followButton = UIButton(type: .system)

    func setup() {
        titleLabel.textAlignment = .left
        followButton.contentHorizontalAlignment = .right
        titleLabel.leftAnchor.constraint(equalTo: leftAnchor).isActive = true
        semanticContentAttribute = .forceLeftToRight
    }
}
// test line
