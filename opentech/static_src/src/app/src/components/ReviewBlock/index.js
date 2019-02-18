import React from 'react'
import PropTypes from 'prop-types'

import EmptyPanel from '@components/EmptyPanel';

const Review = ({ review }) => {
    const { reviewUrl, author, score, recommendation } = review

    return (
        <p>
            <a target="_blank" rel="noopener noreferrer" href={reviewUrl}>
                {author} - {score} - {recommendation.display}
            </a>
        </p>
    )
}

Review.propTypes = {
    review: PropTypes.shape({
        author: PropTypes.string.isRequired,
        score: PropTypes.number.isRequired,
        recommendation: PropTypes.shape({
            display: PropTypes.string.isRequired,
        }).isRequired,
        reviewUrl: PropTypes.string.isRequired,
    }),
}

const ReviewBlock = ({ review }) => {
    const renderReviews = () => {
        if (review === undefined) {
            return null
        } else if (review.reviews.length === 0) {
            return <EmptyPanel column="reviews" />
        }

        return review.reviews.map(review =>
            <Review key={review.id} {...{ review }} />)
    }

    return (
        <div>
            <h1>Reviews &amp; assigness</h1>
            {review && review.recommendation.display &&
                <p>Recommendation: {review.recommendation.display}</p>
            }
            {renderReviews()}
        </div>
    )
}

ReviewBlock.propTypes = {
    review: PropTypes.shape({
        reviews: PropTypes.arrayOf(PropTypes.shape({
            id: PropTypes.number,
        })),
    }),
}

export default ReviewBlock
